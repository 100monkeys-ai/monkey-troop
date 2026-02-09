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
    ChatCompletionRequest, AuthorizeRequest, AuthorizeResponse, ModelsResponse,
    retry_with_backoff, TroopError, TroopResult, AUTH_TIMEOUT, INFERENCE_TIMEOUT
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
    
    // Phase 1: Discovery & Authorization (with retry)
    let auth_response = match get_authorization(&config, &payload.model).await {
        Ok(resp) => resp,
        Err(e) => {
            error!("Authorization failed: {}", e);
            return Err(StatusCode::BAD_GATEWAY);
        }
    };
    
    info!("✓ Got ticket for node: {}", auth_response.target_ip);
    
    // Phase 2: P2P Connection to worker (with retry)
    let response = match send_to_worker(&auth_response, &payload).await {
        Ok(resp) => resp,
        Err(e) => {
            error!("Worker request failed: {}", e);
            return Err(StatusCode::BAD_GATEWAY);
        }
    };
    
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

async fn get_authorization(config: &Config, model: &str) -> TroopResult<AuthorizeResponse> {
    let config = config.clone();
    let model = model.to_string();
    
    retry_with_backoff("Authorization", || {
        let config = config.clone();
        let model = model.clone();
        async move {
            let client = reqwest::Client::new();
            let auth_url = format!("{}/authorize", config.coordinator_url);
            
            let auth_request = AuthorizeRequest {
                model: model.clone(),
                requester: config.requester_id.clone(),
            };
            
            info!("🎫 Requesting authorization ticket...");
            
            let response = client
                .post(&auth_url)
                .json(&auth_request)
                .timeout(AUTH_TIMEOUT)
                .send()
                .await?;
            
            let auth_response: AuthorizeResponse = response.json().await?;
            Ok(auth_response)
        }
    }).await
}

async fn send_to_worker(auth: &AuthorizeResponse, payload: &ChatCompletionRequest) -> TroopResult<reqwest::Response> {
    let auth = auth.clone();
    let payload = payload.clone();
    
    retry_with_backoff("Worker request", || {
        let auth = auth.clone();
        let payload = payload.clone();
        async move {
            let client = reqwest::Client::new();
            let worker_url = format!("http://{}:8080/v1/chat/completions", auth.target_ip);
            
            info!("🔌 Connecting P2P to worker: {}", worker_url);
            
            let response = client
                .post(&worker_url)
                .header("Authorization", format!("Bearer {}", auth.token))
                .json(&payload)
                .timeout(INFERENCE_TIMEOUT)
                .send()
                .await?;
            
            if !response.status().is_success() {
                return Err(TroopError::WorkerUnavailable(
                    format!("Worker returned status {}", response.status())
                ));
            }
            
            Ok(response)
        }
    }).await
}
