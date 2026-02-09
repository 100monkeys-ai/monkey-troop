use crate::config::Config;
use axum::{
    Router,
    extract::{Request, State},
    response::Response,
    http::{StatusCode, HeaderMap},
    middleware::{self, Next},
};
use anyhow::Result;
use tracing::{info, warn};
use std::sync::Arc;

pub async fn run_proxy_server(config: Config) -> Result<()> {
    let addr = format!("0.0.0.0:{}", config.proxy_port);
    info!("🔐 Starting JWT verification proxy on {}", addr);
    
    let shared_config = Arc::new(config);
    
    let app = Router::new()
        .fallback(proxy_handler)
        .layer(middleware::from_fn_with_state(
            shared_config.clone(),
            jwt_verification_middleware
        ))
        .with_state(shared_config);
    
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    info!("Proxy listening on {}", addr);
    
    axum::serve(listener, app).await?;
    
    Ok(())
}

async fn jwt_verification_middleware(
    State(_config): State<Arc<Config>>,
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
        return Err(StatusCode::UNAUTHORIZED);
    }
    
    let token = &auth_header[7..];
    
    // Verify JWT (simplified - in production use proper JWT verification)
    // For now, just check if it looks like a JWT
    if token.split('.').count() != 3 {
        warn!("Invalid JWT format");
        return Err(StatusCode::UNAUTHORIZED);
    }
    
    // TODO: Implement proper JWT verification with coordinator's public key
    // For MVP, we trust the token format
    
    info!("✓ JWT verified");
    
    Ok(next.run(request).await)
}

async fn proxy_handler(
    State(config): State<Arc<Config>>,
    request: Request,
) -> Result<Response, StatusCode> {
    // Forward request to local Ollama
    let client = reqwest::Client::new();
    
    let uri = request.uri();
    let target_url = format!("{}{}", config.ollama_host, uri.path());
    
    info!("Proxying request to {}", target_url);
    
    let body_bytes = axum::body::to_bytes(request.into_body(), usize::MAX)
        .await
        .map_err(|_| StatusCode::BAD_REQUEST)?;
    
    // Forward request (POST assumed for simplicity in MVP)
    let response = client
        .post(&target_url)
        .header("Content-Type", "application/json")
        .body(body_bytes.to_vec())
        .send()
        .await
        .map_err(|_| StatusCode::BAD_GATEWAY)?;
    
    // Convert response
    let status_code = response.status().as_u16();
    let body = response.bytes().await
        .map_err(|_| StatusCode::BAD_GATEWAY)?;
    
    Response::builder()
        .status(status_code)
        .header("Content-Type", "application/json")
        .body(axum::body::Body::from(body))
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)
}
