use crate::application::services::WorkerService;
use crate::domain::inference::{
    ChatMessage, ChatMessageDelta, InferenceChoice, InferenceRequest, InferenceResponse,
    StreamingChoice, StreamingChunk, TokenUsage,
};
use axum::{
    extract::{Json, State},
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    routing::post,
    Router,
};
use bytes::Bytes;
use http_body::Frame;
use http_body_util::StreamBody;
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
    Json(raw): Json<Value>,
) -> Result<Response, StatusCode> {
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

    // 2. Detect E2E encryption and decrypt if present
    let (payload, session_key) = if let Some(e2e_value) = raw.get("e2e") {
        let envelope: monkey_troop_shared::EncryptedPayload =
            serde_json::from_value(e2e_value.clone()).map_err(|_| StatusCode::BAD_REQUEST)?;

        let client_pub = envelope
            .client_public_key
            .as_ref()
            .ok_or(StatusCode::BAD_REQUEST)?;

        let key = state
            .service
            .derive_e2e_session_key(client_pub)
            .map_err(|_| StatusCode::BAD_REQUEST)?;

        let plaintext = monkey_troop_shared::decrypt_payload(&key, &envelope)
            .map_err(|_| StatusCode::BAD_REQUEST)?;

        let req: InferenceRequest =
            serde_json::from_slice(&plaintext).map_err(|_| StatusCode::BAD_REQUEST)?;

        (req, Some(key))
    } else {
        let req: InferenceRequest =
            serde_json::from_value(raw).map_err(|_| StatusCode::BAD_REQUEST)?;
        (req, None)
    };

    // 3. Business Logic: Delegate to Application Service
    info!(
        "Authorized inference request for model {} on node {}",
        payload.model_id, state.service.node_id
    );

    // Verify model exists in registry (supports lookup by name or content hash)
    let registry = state.service.registry.read().await;
    let resolved_model = if payload.model_id.starts_with("sha256:") {
        registry.find_by_hash(&payload.model_id)
    } else {
        registry.find_by_name(&payload.model_id)
    };
    let resolved_model_id = match resolved_model {
        Some(m) => m.id.clone(),
        None => return Err(StatusCode::NOT_FOUND),
    };
    // Explicitly drop the read lock before proceeding to response construction.
    drop(registry);

    // 4. Routing: Select engine and forward
    // For MVP, return mock response. In production, this would call engine.chat()
    if payload.stream {
        return Ok(build_streaming_response(resolved_model_id, session_key));
    }

    let response = InferenceResponse {
        id: "chatcmpl-123".to_string(),
        object: "chat.completion".to_string(),
        created: 1677652288,
        model: resolved_model_id,
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

    let response_json =
        serde_json::to_vec(&response).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if let Some(key) = session_key {
        let encrypted = monkey_troop_shared::encrypt_payload(&key, &response_json)
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        let envelope = monkey_troop_shared::E2EEnvelope { e2e: encrypted };
        let value =
            serde_json::to_value(envelope).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        Ok(Json(value).into_response())
    } else {
        let value =
            serde_json::to_value(response).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        Ok(Json(value).into_response())
    }
}

fn build_streaming_response(model_id: String, session_key: Option<[u8; 32]>) -> Response {
    let chunks = vec![
        StreamingChunk {
            id: "chatcmpl-123".to_string(),
            object: "chat.completion.chunk".to_string(),
            created: 1_677_652_288,
            model: model_id.clone(),
            choices: vec![StreamingChoice {
                index: 0,
                delta: ChatMessageDelta {
                    role: Some("assistant".to_string()),
                    content: Some("Hello".to_string()),
                },
                finish_reason: None,
            }],
        },
        StreamingChunk {
            id: "chatcmpl-123".to_string(),
            object: "chat.completion.chunk".to_string(),
            created: 1_677_652_288,
            model: model_id,
            choices: vec![StreamingChoice {
                index: 0,
                delta: ChatMessageDelta {
                    role: None,
                    content: Some("!".to_string()),
                },
                finish_reason: Some("stop".to_string()),
            }],
        },
    ];

    let chunks_len = chunks.len();

    let sse_events: Vec<Result<Frame<Bytes>, std::convert::Infallible>> =
        if let Some(key) = session_key {
            let base_nonce = monkey_troop_shared::generate_base_nonce();
            chunks
                .into_iter()
                .enumerate()
                .map(|(seq, chunk)| {
                    let json_str = serde_json::to_string(&chunk).unwrap_or_default();
                    let encrypted = monkey_troop_shared::encrypt_chunk(
                        &key,
                        &base_nonce,
                        seq as u32,
                        json_str.as_bytes(),
                    )
                    .expect("Chunk encryption should not fail");
                    let envelope = monkey_troop_shared::E2EChunkEnvelope { e2e: encrypted };
                    let envelope_json = serde_json::to_string(&envelope).unwrap_or_default();
                    Ok(Frame::data(Bytes::from(format!(
                        "data: {envelope_json}\n\n"
                    ))))
                })
                .chain(std::iter::once({
                    let done_encrypted = monkey_troop_shared::encrypt_chunk(
                        &key,
                        &base_nonce,
                        chunks_len as u32,
                        b"[DONE]",
                    )
                    .expect("Chunk encryption should not fail");
                    let done_envelope = monkey_troop_shared::E2EChunkEnvelope {
                        e2e: done_encrypted,
                    };
                    let done_json = serde_json::to_string(&done_envelope).unwrap_or_default();
                    Ok(Frame::data(Bytes::from(format!("data: {done_json}\n\n"))))
                }))
                .collect()
        } else {
            chunks
                .into_iter()
                .map(|chunk| {
                    let json_str = serde_json::to_string(&chunk).unwrap_or_default();
                    Ok(Frame::data(Bytes::from(format!("data: {json_str}\n\n"))))
                })
                .chain(std::iter::once(Ok(Frame::data(Bytes::from(
                    "data: [DONE]\n\n",
                )))))
                .collect()
        };

    let stream = futures_util::stream::iter(sse_events);
    let body = StreamBody::new(stream);

    Response::builder()
        .header("Content-Type", "text/event-stream")
        .header("Cache-Control", "no-cache")
        .header("Connection", "keep-alive")
        .body(axum::body::Body::new(body))
        .unwrap()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::application::ports::{
        AuthTokenVerifier, CoordinatorClient, E2EDecryptor, HardwareMonitor,
    };
    use crate::domain::models::{EngineType, HardwareStatus, Model, ModelRegistry};
    use anyhow::Result;
    use async_trait::async_trait;
    use axum::body::Body;
    use axum::http::{Request, StatusCode};
    use monkey_troop_shared::ModelIdentity;
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
            _: Vec<ModelIdentity>,
            _: HardwareStatus,
            _: Vec<String>,
            _: Option<String>,
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

    struct MockE2EDecryptor;
    impl E2EDecryptor for MockE2EDecryptor {
        fn public_key_b64(&self) -> &str {
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        }
        fn derive_session_key(&self, _client_public_key_b64: &str) -> anyhow::Result<[u8; 32]> {
            Ok([0u8; 32])
        }
    }

    fn make_service(valid_auth: bool, models: Vec<Model>) -> Arc<WorkerService> {
        let registry = Arc::new(RwLock::new(ModelRegistry::new()));
        // We need to add models synchronously for tests, so use try_write
        let mut reg = registry.try_write().unwrap();
        for m in models {
            reg.add_model(m);
        }
        drop(reg);

        Arc::new(WorkerService::new(
            "node-1".to_string(),
            registry,
            vec![],
            Arc::new(MockMonitor),
            Arc::new(MockCoordinator),
            Arc::new(MockVerifier { valid: valid_auth }),
            Arc::new(MockE2EDecryptor),
        ))
    }

    #[tokio::test]
    async fn test_proxy_auth_success() {
        let service = make_service(
            true,
            vec![Model {
                id: "llama3".to_string(),
                content_hash: "sha256:abc123".to_string(),
                size_bytes: 4_000_000_000,
                engine_type: EngineType::Ollama,
            }],
        );

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
        let service = make_service(false, vec![]);

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
        let service = make_service(true, vec![]);

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

    #[tokio::test]
    async fn test_proxy_e2e_encrypted_request() {
        let service = make_service(
            true,
            vec![Model {
                id: "llama3".to_string(),
                content_hash: "sha256:abc123".to_string(),
                size_bytes: 4_000_000_000,
                engine_type: EngineType::Ollama,
            }],
        );

        let app = create_proxy_router(Arc::new(ProxyState { service }));

        // The MockE2EDecryptor returns [0u8; 32] as session key
        let key = [0u8; 32];
        let plaintext =
            serde_json::to_vec(&json!({"model_id": "llama3", "messages": [], "stream": false}))
                .unwrap();
        let encrypted = monkey_troop_shared::encrypt_payload(&key, &plaintext).unwrap();
        let mut encrypted_with_key = encrypted;
        encrypted_with_key.client_public_key =
            Some("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=".to_string());

        let envelope = json!({ "e2e": encrypted_with_key });

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/v1/chat/completions")
                    .header("Authorization", "Bearer valid-token")
                    .header("Content-Type", "application/json")
                    .body(Body::from(serde_json::to_string(&envelope).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);

        // Response should be E2E encrypted (contains "e2e" field)
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let body_json: Value = serde_json::from_slice(&body).unwrap();
        assert!(body_json.get("e2e").is_some());

        // Decrypt and verify
        let response_envelope: monkey_troop_shared::E2EEnvelope =
            serde_json::from_value(body_json).unwrap();
        let decrypted = monkey_troop_shared::decrypt_payload(&key, &response_envelope.e2e).unwrap();
        let response_data: Value = serde_json::from_slice(&decrypted).unwrap();
        assert_eq!(response_data["model"], "llama3");
    }

    #[tokio::test]
    async fn test_proxy_e2e_missing_client_key() {
        let service = make_service(
            true,
            vec![Model {
                id: "llama3".to_string(),
                content_hash: "sha256:abc123".to_string(),
                size_bytes: 4_000_000_000,
                engine_type: EngineType::Ollama,
            }],
        );

        let app = create_proxy_router(Arc::new(ProxyState { service }));

        // E2E envelope without client_public_key
        let key = [0u8; 32];
        let plaintext =
            serde_json::to_vec(&json!({"model_id": "llama3", "messages": [], "stream": false}))
                .unwrap();
        let encrypted = monkey_troop_shared::encrypt_payload(&key, &plaintext).unwrap();
        // client_public_key is None by default from encrypt_payload
        let envelope = json!({ "e2e": encrypted });

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/v1/chat/completions")
                    .header("Authorization", "Bearer valid-token")
                    .header("Content-Type", "application/json")
                    .body(Body::from(serde_json::to_string(&envelope).unwrap()))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn test_proxy_streaming_response() {
        let service = make_service(
            true,
            vec![Model {
                id: "llama3".to_string(),
                content_hash: "sha256:abc123".to_string(),
                size_bytes: 4_000_000_000,
                engine_type: EngineType::Ollama,
            }],
        );

        let app = create_proxy_router(Arc::new(ProxyState { service }));

        let response = app
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri("/v1/chat/completions")
                    .header("Authorization", "Bearer valid-token")
                    .header("Content-Type", "application/json")
                    .body(Body::from(
                        json!({"model_id": "llama3", "messages": [], "stream": true}).to_string(),
                    ))
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        assert_eq!(
            response.headers().get("Content-Type").unwrap(),
            "text/event-stream"
        );
    }
}
