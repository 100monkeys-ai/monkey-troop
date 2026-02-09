use crate::config::Config;
use axum::{
    Router,
    extract::{Request, State},
    response::Response,
    http::{StatusCode, HeaderMap},
    middleware::{self, Next},
};
use anyhow::Result;
use tracing::{info, warn, error};
use std::sync::Arc;
use tokio::sync::RwLock;
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
struct JwtClaims {
    sub: String,
    aud: String,
    exp: usize,
}

struct ProxyState {
    config: Config,
    public_key: RwLock<Option<DecodingKey>>,
}

pub async fn run_proxy_server(config: Config) -> Result<()> {
    let addr = format!("0.0.0.0:{}", config.proxy_port);
    info!("🔐 Starting JWT verification proxy on {}", addr);
    
    let state = Arc::new(ProxyState {
        config: config.clone(),
        public_key: RwLock::new(None),
    });
    
    // Fetch public key from coordinator on startup
    match fetch_public_key(&config.coordinator_url).await {
        Ok(key) => {
            *state.public_key.write().await = Some(key);
            info!("✓ Public key loaded from coordinator");
        }
        Err(e) => {
            error!("Failed to fetch public key: {}", e);
            return Err(e);
        }
    }
    
    let app = Router::new()
        .fallback(proxy_handler)
        .layer(middleware::from_fn_with_state(
            state.clone(),
            jwt_verification_middleware
        ))
        .with_state(state);
    
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    info!("Proxy listening on {}", addr);
    
    axum::serve(listener, app).await?;
    
    Ok(())
}

async fn fetch_public_key(coordinator_url: &str) -> Result<DecodingKey> {
    let client = reqwest::Client::new();
    let url = format!("{}/public-key", coordinator_url);
    
    let response = client.get(&url)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await?;
    
    let pem_string = response.text().await?;
    
    let key = DecodingKey::from_rsa_pem(pem_string.as_bytes())
        .map_err(|e| anyhow::anyhow!("Failed to parse public key: {}", e))?;
    
    Ok(key)
}

async fn jwt_verification_middleware(
    State(state): State<Arc<ProxyState>>,
    headers: HeaderMap,
    request: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    // Extract Authorization header
    let auth_header = headers
        .get("Authorization")
        .and_then(|h| h.to_str().ok())
        .ok_or(StatusCode::UNAUTHORIZED)?;
    
    if !auth_header.starts_with("Bearer ") {
        warn!("Invalid Authorization header format");
        return Err(StatusCode::UNAUTHORIZED);
    }
    
    let token = &auth_header[7..];
    
    // Get public key from state
    let public_key_guard = state.public_key.read().await;
    let public_key = public_key_guard.as_ref()
        .ok_or_else(|| {
            error!("Public key not loaded");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    
    // Verify JWT signature
    let mut validation = Validation::new(Algorithm::RS256);
    validation.set_audience(&["troop-worker"]);
    
    match decode::<JwtClaims>(token, public_key, &validation) {
        Ok(token_data) => {
            info!("✓ JWT verified for node: {}", token_data.claims.sub);
            Ok(next.run(request).await)
        }
        Err(e) => {
            warn!("JWT verification failed: {}", e);
            Err(StatusCode::UNAUTHORIZED)
        }
    }
}

async fn proxy_handler(
    State(state): State<Arc<ProxyState>>,
    request: Request,
) -> Result<Response, StatusCode> {
    // Forward request to local Ollama
    let client = reqwest::Client::new();
    
    let uri = request.uri();
    let target_url = format!("{}{}", state.config.ollama_host, uri.path());
    
    info!("Proxying request to {}", target_url);
    
    let body_bytes = axum::body::to_bytes(request.into_body(), usize::MAX)
        .await
        .map_err(|_| StatusCode::BAD_REQUEST)?;
    
    // Check if streaming is requested
    let is_stream = if let Ok(json) = serde_json::from_slice::<serde_json::Value>(&body_bytes) {
        json.get("stream").and_then(|v| v.as_bool()).unwrap_or(false)
    } else {
        false
    };
    
    // Forward request (POST assumed for simplicity in MVP)
    let response = client
        .post(&target_url)
        .header("Content-Type", "application/json")
        .body(body_bytes.to_vec())
        .send()
        .await
        .map_err(|_| StatusCode::BAD_GATEWAY)?;
    
    let status = response.status();
    let status_code = status.as_u16();
    
    // Handle streaming vs non-streaming responses
    if is_stream {
        // Pass through the stream directly without buffering
        info!("✓ Streaming response from Ollama");
        Response::builder()
            .status(status_code)
            .header("Content-Type", "text/event-stream")
            .header("Cache-Control", "no-cache")
            .header("Connection", "keep-alive")
            .body(axum::body::Body::from_stream(response.bytes_stream()))
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)
    } else {
        // Buffer complete response for non-streaming
        let body = response.bytes().await
            .map_err(|_| StatusCode::BAD_GATEWAY)?;
        
        Response::builder()
            .status(status_code)
            .header("Content-Type", "application/json")
            .body(axum::body::Body::from(body))
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)
    }
}
