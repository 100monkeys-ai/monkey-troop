use crate::config::Config;
use anyhow::Result;

use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use monkey_troop_shared::{
    retry_with_backoff, AuthorizeRequest, AuthorizeResponse, ChatCompletionRequest, ModelsResponse,
    TroopResult, AUTH_TIMEOUT, INFERENCE_TIMEOUT,
};
use std::sync::Arc;
use tracing::{error, info};
use url::Url;

pub async fn run_proxy_server(config: Config) -> Result<()> {
    let addr = format!("127.0.0.1:{}", config.proxy_port);
    info!("🚀 Starting OpenAI-compatible proxy on {}", addr);
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
        "✓ Proxy ready at http://localhost:{}",
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
    info!("📋 Fetching available models from coordinator");

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
        "💬 Received chat completion request for model: {}",
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

    info!("✓ Got ticket for node: {}", auth_response.target_ip);

    // Step 2: P2P Connection to worker (with retry)
    let is_stream = payload.stream;
    let response = match send_to_worker(&auth_response, &payload, config.worker_port).await {
        Ok(resp) => resp,
        Err(e) => {
            error!("Worker request failed: {}", e);
            return Err(StatusCode::BAD_GATEWAY);
        }
    };

    let status_code = response.status();
    let status_u16 = status_code.as_u16();

    // Handle streaming vs non-streaming responses
    if is_stream {
        // For successful streaming responses, set SSE-specific headers.
        // For error responses, avoid forcing `content-type: text/event-stream`
        // so that the worker's original content type can be respected.
        info!("✓ Streaming response back to client");
        if status_code.is_success() {
            Ok(Response::builder()
                .status(status_u16)
                .header("content-type", "text/event-stream")
                .header("cache-control", "no-cache")
                .body(axum::body::Body::from_stream(response.bytes_stream()))
                .map_err(|e| {
                    error!("Failed to build streaming response: {}", e);
                    StatusCode::INTERNAL_SERVER_ERROR
                })?)
        } else {
            Ok(Response::builder()
                .status(status_u16)
                .body(axum::body::Body::from_stream(response.bytes_stream()))
                .map_err(|e| {
                    error!("Failed to build streaming error response: {}", e);
                    StatusCode::INTERNAL_SERVER_ERROR
                })?)
        }
    } else {
        // Buffer complete response for non-streaming
        let headers = response.headers().clone();
        let body = response.bytes().await.map_err(|e| {
            error!("Failed to read response body: {}", e);
            StatusCode::BAD_GATEWAY
        })?;

        info!("✓ Response received, forwarding to client");

        // Hop-by-hop headers must not be forwarded by a proxy.
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

        let mut builder = Response::builder().status(status_u16);
        if let Some(builder_headers) = builder.headers_mut() {
            for (name, value) in &headers {
                if !HOP_BY_HOP.contains(&name.as_str()) {
                    builder_headers.insert(name, value.clone());
                }
            }
        }

        Ok(builder.body(axum::body::Body::from(body)).map_err(|e| {
            error!("Failed to build response: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?)
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

            info!("🎫 Requesting authorization ticket...");

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
) -> TroopResult<reqwest::Response> {
    retry_with_backoff("Worker request", || {
        let auth = auth.clone();
        let payload = payload.clone();
        async move {
            let client = reqwest::Client::new();
            let worker_url_str = format!(
                "http://{}:{}/v1/chat/completions",
                auth.target_ip, worker_port
            );
            let worker_url = Url::parse(&worker_url_str).map_err(anyhow::Error::from)?;

            info!("🔌 Connecting P2P to worker: {}", worker_url);

            let response = client
                .post(worker_url)
                .header("Authorization", format!("Bearer {}", auth.token))
                .json(&payload)
                .timeout(INFERENCE_TIMEOUT)
                .send()
                .await?;

            Ok(response)
        }
    })
    .await
}
