use crate::application::services::WorkerService;
use crate::domain::inference::{
    ChatMessage, InferenceChoice, InferenceRequest, InferenceResponse, TokenUsage,
};
use axum::{
    extract::{Json, State},
    http::{HeaderMap, StatusCode},
    routing::post,
    Router,
};
use serde_json::Value;
use std::sync::Arc;
use tracing::info;

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
    let auth_header = headers
        .get("Authorization")
        .and_then(|h| h.to_str().ok())
        .and_then(|s| s.strip_prefix("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;

    if !state
        .service
        .verify_ticket(auth_header)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
    {
        return Err(StatusCode::UNAUTHORIZED);
    }

    // 2. Business Logic: Delegate to Application Service
    info!(
        "Authorized inference request for model {} on node {}",
        payload.model_id, state.service.node_id
    );

    // Verify model exists in registry
    let registry = state.service.registry.read().await;
    if !registry.get_model_ids().contains(&payload.model_id) {
        return Err(StatusCode::NOT_FOUND);
    }
    // Explicitly drop the read lock before proceeding to response construction.
    drop(registry);

    // 3. Routing: Select engine and forward
    // For MVP, return mock response. In production, this would call engine.chat()
    let response = InferenceResponse {
        id: "chatcmpl-123".to_string(),
        object: "chat.completion".to_string(),
        created: 1677652288,
        model: payload.model_id,
        choices: vec![InferenceChoice {
            index: 0,
            message: ChatMessage {
                role: "assistant".to_string(),
                content: "Hello! I am a Monkey Troop Worker node.".to_string(),
            },
            finish_reason: "stop".to_string(),
        }],
        usage: TokenUsage {
            prompt_tokens: 9,
            completion_tokens: 12,
            total_tokens: 21,
        },
    };

    Ok(Json(
        serde_json::to_value(response).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::application::ports::{AuthTokenVerifier, CoordinatorClient, HardwareMonitor};
    use crate::domain::models::{EngineType, HardwareStatus, Model, ModelRegistry};
    use anyhow::Result;
    use async_trait::async_trait;
    use axum::body::Body;
    use axum::http::{Request, StatusCode};
    use serde_json::json;
    use tokio::sync::RwLock;
    use tower::ServiceExt;

    struct MockMonitor;
    #[async_trait]
    impl HardwareMonitor for MockMonitor {
        async fn get_status(&self) -> Result<HardwareStatus> {
            Ok(HardwareStatus {
                gpu_name: "test".to_string(),
                vram_free_mb: 0,
            })
        }
        async fn is_idle(&self) -> Result<bool> {
            Ok(true)
        }
    }

    struct MockCoordinator;
    #[async_trait]
    impl CoordinatorClient for MockCoordinator {
        async fn send_heartbeat(
            &self,
            _: &str,
            _: crate::domain::models::NodeStatus,
            _: Vec<String>,
            _: HardwareStatus,
        ) -> Result<()> {
            Ok(())
        }
    }

    struct MockVerifier {
        valid: bool,
    }
    #[async_trait]
    impl AuthTokenVerifier for MockVerifier {
        async fn verify_ticket(&self, _: &str, _: &str) -> Result<bool> {
            Ok(self.valid)
        }
    }

    #[tokio::test]
    async fn test_proxy_auth_success() {
        let registry = Arc::new(RwLock::new(ModelRegistry::new()));
        registry.write().await.add_model(Model {
            id: "llama3".to_string(),
            engine_type: EngineType::Ollama,
        });

        let service = Arc::new(WorkerService::new(
            "node-1".to_string(),
            registry,
            vec![],
            Arc::new(MockMonitor),
            Arc::new(MockCoordinator),
            Arc::new(MockVerifier { valid: true }),
        ));

        let app = create_proxy_router(Arc::new(ProxyState { service }));

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/v1/chat/completions")
                    .header("Authorization", "Bearer valid-token")
                    .header("Content-Type", "application/json")
                    .body(Body::from(
                        json!({"model_id": "llama3", "messages": [], "stream": false}).to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
    }

    #[tokio::test]
    async fn test_proxy_auth_failure() {
        let service = Arc::new(WorkerService::new(
            "node-1".to_string(),
            Arc::new(RwLock::new(ModelRegistry::new())),
            vec![],
            Arc::new(MockMonitor),
            Arc::new(MockCoordinator),
            Arc::new(MockVerifier { valid: false }),
        ));

        let app = create_proxy_router(Arc::new(ProxyState { service }));

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/v1/chat/completions")
                    .header("Authorization", "Bearer invalid-token")
                    .header("Content-Type", "application/json")
                    .body(Body::from(
                        json!({"model_id": "llama3", "messages": [], "stream": false}).to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn test_proxy_model_not_found() {
        let service = Arc::new(WorkerService::new(
            "node-1".to_string(),
            Arc::new(RwLock::new(ModelRegistry::new())),
            vec![],
            Arc::new(MockMonitor),
            Arc::new(MockCoordinator),
            Arc::new(MockVerifier { valid: true }),
        ));

        let app = create_proxy_router(Arc::new(ProxyState { service }));

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/v1/chat/completions")
                    .header("Authorization", "Bearer valid-token")
                    .header("Content-Type", "application/json")
                    .body(Body::from(
                        json!({"model_id": "non-existent", "messages": [], "stream": false})
                            .to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::NOT_FOUND);
    }
}
