use crate::config::Config;
use anyhow::Result;

use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use futures::StreamExt;
use monkey_troop_shared::{
    retry_with_backoff, AuthorizeRequest, AuthorizeResponse, ChatCompletionRequest, ModelsResponse,
    TroopError, TroopResult, AUTH_TIMEOUT, INFERENCE_TIMEOUT,
};
use axum::http::HeaderName;
use std::collections::HashSet;
use std::sync::Arc;
use tracing::{error, info};
use url::Url;

// Standard HTTP hop-by-hop headers that must not be forwarded by a proxy (RFC 7230).
const HOP_BY_HOP: &[&str] = &[
    "connection",
    "keep-alive",
    "transfer-encoding",
    "te",
    "trailer",
    "upgrade",
    "proxy-authorization",
    "proxy-authenticate",
];

/// Copies end-to-end headers from `src` into `dst`, skipping hop-by-hop headers and any
/// headers nominated by the `Connection` header value (RFC 7230 §6.1). Uses `append` to
/// preserve multi-valued headers such as `set-cookie`.
fn copy_end_to_end_headers(src: &axum::http::HeaderMap, dst: &mut axum::http::HeaderMap) {
    let connection_nominated: HashSet<HeaderName> = src
        .get(axum::http::header::CONNECTION)
        .and_then(|v| v.to_str().ok())
        .map(|s| {
            s.split(',')
                .filter_map(|t| {
                    let t = t.trim();
                    if t.is_empty() {
                        None
                    } else {
                        t.parse::<HeaderName>().ok()
                    }
                })
                .collect()
        })
        .unwrap_or_default();

    for (name, value) in src {
        let name_str = name.as_str();
        if HOP_BY_HOP.contains(&name_str) {
            continue;
        }
        if connection_nominated.contains(name) {
            continue;
        }
        dst.append(name, value.clone());
    }
}

pub async fn run_proxy_server(config: Config) -> Result<()> {
    let addr = format!("127.0.0.1:{}", config.proxy_port);
    info!("Starting OpenAI-compatible proxy on {}", addr);
    info!(
        "   Point your AI tools to: http://localhost:{}/v1",
        config.proxy_port
    );

    let shared_config = Arc::new(config);

    let app = Router::new()
        .route("/v1/chat/completions", post(chat_completions_handler))
        .route("/v1/models", get(list_models_handler))
        .route("/health", get(health_handler))
        .with_state(shared_config.clone());

    let listener = tokio::net::TcpListener::bind(&addr).await?;
    info!(
        "Proxy ready at http://localhost:{}",
        shared_config.proxy_port
    );

    axum::serve(listener, app).await?;

    Ok(())
}

async fn health_handler() -> impl IntoResponse {
    Json(serde_json::json!({
        "status": "healthy",
        "service": "monkey-troop-client"
    }))
}

async fn list_models_handler(
    State(config): State<Arc<Config>>,
) -> Result<Json<ModelsResponse>, StatusCode> {
    info!("Fetching available models from coordinator");

    let client = reqwest::Client::new();
    let url = config.coordinator_url.join("v1/models").map_err(|e| {
        error!(
            "Failed to construct models URL from base '{}' and path 'v1/models': {}",
            config.coordinator_url, e
        );
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let url_str = url.to_string();
    let response = client.get(url).send().await.map_err(|e| {
        error!("Failed to fetch models from '{}': {}", url_str, e);
        StatusCode::BAD_GATEWAY
    })?;

    let models: ModelsResponse = response.json().await.map_err(|e| {
        error!("Failed to deserialize models response: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(models))
}

async fn chat_completions_handler(
    State(config): State<Arc<Config>>,
    Json(payload): Json<ChatCompletionRequest>,
) -> Result<Response, StatusCode> {
    info!(
        "Received chat completion request for model: {}",
        payload.model
    );

    // Step 1: Discovery & Authorization (with retry)
    let auth_response = match get_authorization(&config, &payload.model).await {
        Ok(resp) => resp,
        Err(e) => {
            error!("Authorization failed: {}", e);
            return Err(StatusCode::BAD_GATEWAY);
        }
    };

    info!("Got ticket for node: {}", auth_response.target_ip);

    // Step 2: Establish E2E session if worker supports encryption
    let e2e_session = if let Some(ref worker_pub_key) = auth_response.encryption_public_key {
        match crate::e2e_crypto::establish_session(worker_pub_key) {
            Ok(session) => {
                info!("E2E encryption session established");
                Some(session)
            }
            Err(e) => {
                error!("E2E session establishment failed: {}", e);
                return Err(StatusCode::INTERNAL_SERVER_ERROR);
            }
        }
    } else {
        None
    };

    // Step 3: Send to worker (encrypted or plaintext)
    let is_stream = payload.stream;
    let response = match send_to_worker(
        &auth_response,
        &payload,
        config.worker_port,
        e2e_session.as_ref(),
    )
    .await
    {
        Ok(resp) => resp,
        Err(e) => {
            error!("Worker request failed: {}", e);
            return Err(StatusCode::BAD_GATEWAY);
        }
    };

    let status_code = response.status();
    let status_u16 = status_code.as_u16();

    // Step 4: Handle response (decrypt if E2E)
    if is_stream {
        if !status_code.is_success() {
            // For error responses, forward worker headers without forcing SSE content-type.
            let worker_headers = response.headers().clone();
            let mut builder = Response::builder().status(status_u16);
            if let Some(builder_headers) = builder.headers_mut() {
                copy_end_to_end_headers(&worker_headers, builder_headers);
            }
            return builder
                .body(axum::body::Body::from_stream(response.bytes_stream()))
                .map_err(|e| {
                    error!("Failed to build streaming error response: {}", e);
                    StatusCode::INTERNAL_SERVER_ERROR
                });
        }

        if let Some(ref session) = e2e_session {
            // Decrypt each SSE chunk and re-emit as plaintext
            info!("Decrypting streaming response");
            let session_key = session.session_key;
            let byte_stream = response.bytes_stream();

            let decrypted_stream = byte_stream.map(move |chunk_result| {
                match chunk_result {
                    Ok(bytes) => {
                        let text = String::from_utf8_lossy(&bytes);
                        let mut output = String::new();
                        for line in text.split("\n\n") {
                            let line = line.trim();
                            if line.is_empty() {
                                continue;
                            }
                            if let Some(data) = line.strip_prefix("data: ") {
                                match crate::e2e_crypto::decrypt_sse_chunk(&session_key, data) {
                                    Ok(plaintext) => {
                                        output.push_str(&format!("data: {plaintext}\n\n"));
                                    }
                                    Err(e) => {
                                        error!("Failed to decrypt SSE chunk: {}", e);
                                        // Pass through non-decryptable data (e.g. "[DONE]")
                                        output.push_str(&format!("data: {data}\n\n"));
                                    }
                                }
                            }
                        }
                        Ok(bytes::Bytes::from(output))
                    }
                    Err(e) => Err(e),
                }
            });

            Ok(Response::builder()
                .status(status_u16)
                .header("content-type", "text/event-stream")
                .header("cache-control", "no-cache")
                .body(axum::body::Body::from_stream(decrypted_stream))
                .map_err(|e| {
                    error!("Failed to build streaming response: {}", e);
                    StatusCode::INTERNAL_SERVER_ERROR
                })?)
        } else {
            // Plaintext streaming passthrough
            info!("Streaming response back to client");
            Ok(Response::builder()
                .status(status_u16)
                .header("content-type", "text/event-stream")
                .header("cache-control", "no-cache")
                .body(axum::body::Body::from_stream(response.bytes_stream()))
                .map_err(|e| {
                    error!("Failed to build streaming response: {}", e);
                    StatusCode::INTERNAL_SERVER_ERROR
                })?)
        }
    } else {
        let worker_headers = response.headers().clone();
        let body = response.bytes().await.map_err(|e| {
            error!("Failed to read response body: {}", e);
            StatusCode::BAD_GATEWAY
        })?;

        if status_code.is_success() {
            if let Some(ref session) = e2e_session {
                // Decrypt the response
                let decrypted = crate::e2e_crypto::decrypt_response(&session.session_key, &body)
                    .map_err(|e| {
                        error!("Failed to decrypt response: {}", e);
                        StatusCode::INTERNAL_SERVER_ERROR
                    })?;
                info!("Response decrypted, forwarding to client");
                Ok(Response::builder()
                    .status(status_u16)
                    .header("content-type", "application/json")
                    .body(axum::body::Body::from(decrypted))
                    .map_err(|e| {
                        error!("Failed to build response: {}", e);
                        StatusCode::INTERNAL_SERVER_ERROR
                    })?)
            } else {
                // Forward with worker headers (minus hop-by-hop)
                info!("Response received, forwarding to client");
                let mut builder = Response::builder().status(status_u16);
                if let Some(builder_headers) = builder.headers_mut() {
                    copy_end_to_end_headers(&worker_headers, builder_headers);
                }
                Ok(builder.body(axum::body::Body::from(body)).map_err(|e| {
                    error!("Failed to build response: {}", e);
                    StatusCode::INTERNAL_SERVER_ERROR
                })?)
            }
        } else {
            // Error response: forward worker headers (minus hop-by-hop) without modification
            let mut builder = Response::builder().status(status_u16);
            if let Some(builder_headers) = builder.headers_mut() {
                copy_end_to_end_headers(&worker_headers, builder_headers);
            }
            Ok(builder.body(axum::body::Body::from(body)).map_err(|e| {
                error!("Failed to build response: {}", e);
                StatusCode::INTERNAL_SERVER_ERROR
            })?)
        }
    }
}

async fn get_authorization(config: &Config, model: &str) -> TroopResult<AuthorizeResponse> {
    retry_with_backoff("Authorization", || {
        let config = config.clone();
        let model = model.to_string();
        async move {
            let client = reqwest::Client::new();
            let auth_url = config
                .coordinator_url
                .join("authorize")
                .map_err(anyhow::Error::from)?;

            let auth_request = AuthorizeRequest {
                model,
                requester: config.requester_id.clone(),
            };

            info!("Requesting authorization ticket...");

            let response = client
                .post(auth_url)
                .json(&auth_request)
                .timeout(AUTH_TIMEOUT)
                .send()
                .await?;

            let auth_response: AuthorizeResponse = response.json().await?;
            Ok(auth_response)
        }
    })
    .await
}

async fn send_to_worker(
    auth: &AuthorizeResponse,
    payload: &ChatCompletionRequest,
    worker_port: u16,
    e2e_session: Option<&crate::e2e_crypto::E2ESession>,
) -> TroopResult<reqwest::Response> {
    // Pre-compute request body (encrypted or plaintext) before the retry loop
    // so we avoid borrow issues with the session reference inside the closure.
    let request_body: serde_json::Value = if let Some(session) = e2e_session {
        let plaintext =
            serde_json::to_vec(payload).map_err(|e| TroopError::InternalError(e.to_string()))?;
        crate::e2e_crypto::encrypt_request(session, &plaintext)
            .map_err(|e| TroopError::InternalError(e.to_string()))?
    } else {
        serde_json::to_value(payload).map_err(|e| TroopError::InternalError(e.to_string()))?
    };

    retry_with_backoff("Worker request", || {
        let auth = auth.clone();
        let body = request_body.clone();
        async move {
            let client = reqwest::Client::new();
            let worker_url_str = format!(
                "http://{}:{}/v1/chat/completions",
                auth.target_ip, worker_port
            );
            let worker_url = Url::parse(&worker_url_str).map_err(anyhow::Error::from)?;

            info!("Connecting P2P to worker: {}", worker_url);

            let response = client
                .post(worker_url)
                .header("Authorization", format!("Bearer {}", auth.token))
                .json(&body)
                .timeout(INFERENCE_TIMEOUT)
                .send()
                .await?;

            Ok(response)
        }
    })
    .await
}
