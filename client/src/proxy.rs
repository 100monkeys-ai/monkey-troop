use crate::config::Config;
use axum::{
    Router,
    extract::State,
    response::{Response, IntoResponse},
    http::StatusCode,
    routing::{get, post},
    Json,
};
use anyhow::Result;
use tracing::{info, error};
use std::sync::Arc;
use monkey_troop_shared::{
    ChatCompletionRequest, AuthorizeRequest, AuthorizeResponse, ModelsResponse
};

pub async fn run_proxy_server(config: Config) -> Result<()> {
    let addr = format!("127.0.0.1:{}", config.proxy_port);
    info!("🚀 Starting OpenAI-compatible proxy on {}", addr);
    info!("   Point your AI tools to: http://localhost:{}/v1", config.proxy_port);
    
    let shared_config = Arc::new(config);
    
    let app = Router::new()
        .route("/v1/chat/completions", post(chat_completions_handler))
        .route("/v1/models", get(list_models_handler))
        .route("/health", get(health_handler))
        .with_state(shared_config.clone());
    
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    info!("✓ Proxy ready at http://localhost:{}", shared_config.proxy_port);
    
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
    let url = format!("{}/v1/models", config.coordinator_url);
    
    let response = client
        .get(&url)
        .send()
        .await
        .map_err(|e| {
            error!("Failed to fetch models: {}", e);
            StatusCode::BAD_GATEWAY
        })?;
    
    let models: ModelsResponse = response
        .json()
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    
    Ok(Json(models))
}

async fn chat_completions_handler(
    State(config): State<Arc<Config>>,
    Json(payload): Json<ChatCompletionRequest>,
) -> Result<Response, StatusCode> {
    info!("💬 Received chat completion request for model: {}", payload.model);
    
    // Phase 1: Discovery & Authorization
    let client = reqwest::Client::new();
    let auth_url = format!("{}/authorize", config.coordinator_url);
    
    let auth_request = AuthorizeRequest {
        model: payload.model.clone(),
        requester: config.requester_id.clone(),
    };
    
    info!("🎫 Requesting authorization ticket...");
    
    let auth_response: AuthorizeResponse = client
        .post(&auth_url)
        .json(&auth_request)
        .send()
        .await
        .map_err(|e| {
            error!("Authorization request failed: {}", e);
            StatusCode::BAD_GATEWAY
        })?
        .json()
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    
    info!("✓ Got ticket for node: {}", auth_response.target_ip);
    
    // Phase 2: Direct P2P connection to worker
    let worker_url = format!("http://{}:8080/v1/chat/completions", auth_response.target_ip);
    
    info!("⚡ Connecting P2P to worker at {}", worker_url);
    
    // Forward request with JWT ticket
    let response = client
        .post(&worker_url)
        .header("Authorization", format!("Bearer {}", auth_response.token))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await
        .map_err(|e| {
            error!("Worker connection failed: {}", e);
            StatusCode::BAD_GATEWAY
        })?;
    
    // Stream response back to client
    let status_code = response.status().as_u16();
    let body = response.bytes().await
        .map_err(|_| StatusCode::BAD_GATEWAY)?;
    
    info!("✓ Response received, forwarding to client");
    
    Response::builder()
        .status(status_code)
        .body(axum::body::Body::from(body))
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)
}
