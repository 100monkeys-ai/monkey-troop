use axum::{
    extract::{State, HeaderMap},
    routing::post,
    Json, Router,
    http::StatusCode,
};
use std::sync::Arc;
use crate::application::services::WorkerService;
use crate::domain::inference::{InferenceRequest, InferenceResponse};
use serde_json::{json, Value};

pub struct ProxyState {
    pub service: Arc<WorkerService>,
}

pub fn create_proxy_router(state: Arc<ProxyState>) -> Router {
    Router::new()
        .route("/v1/chat/completions", post(handle_chat_completion))
        .with_state(state)
}

async fn handle_chat_completion(
    State(state): State<Arc<ProxyState>>,
    headers: HeaderMap,
    Json(payload): Json<InferenceRequest>,
) -> Result<Json<Value>, StatusCode> {
    // 1. Authentication (JWT verification via Header)
    let auth_header = headers.get("Authorization")
        .and_then(|h| h.to_str().ok())
        .and_then(|s| s.strip_prefix("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;

    // 2. Business Logic: Delegate to Application Service
    // service.verify_ticket(auth_header, ...).await
    
    // 3. Routing: Select engine and forward
    // For MVP, just return a mock response
    Ok(Json(json!({
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": payload.model_id,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello! I am a Monkey Troop Worker node.",
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 9,
            "completion_tokens": 12,
            "total_tokens": 21
        }
    })))
}
