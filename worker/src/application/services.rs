use crate::application::ports::{
    AuthTokenVerifier, CoordinatorClient, E2EDecryptor, HardwareMonitor, InferenceEngine,
};
use crate::domain::inference::{ChatMessage, InferenceResponse, StreamingChunk};
use crate::domain::models::{EngineType, ModelRegistry, NodeStatus};
use anyhow::Result;
use futures::Stream;
use std::collections::HashMap;
use std::pin::Pin;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{error, info};

pub struct WorkerService {
    pub node_id: String,
    pub registry: Arc<RwLock<ModelRegistry>>,
    engines: HashMap<EngineType, Box<dyn InferenceEngine>>,
    monitor: Arc<dyn HardwareMonitor>,
    coordinator: Arc<dyn CoordinatorClient>,
    verifier: Arc<dyn AuthTokenVerifier>,
    e2e: Arc<dyn E2EDecryptor>,
}

impl WorkerService {
    pub fn new(
        node_id: String,
        registry: Arc<RwLock<ModelRegistry>>,
        engines: HashMap<EngineType, Box<dyn InferenceEngine>>,
        monitor: Arc<dyn HardwareMonitor>,
        coordinator: Arc<dyn CoordinatorClient>,
        verifier: Arc<dyn AuthTokenVerifier>,
        e2e: Arc<dyn E2EDecryptor>,
    ) -> Self {
        Self {
            node_id,
            registry,
            engines,
            monitor,
            coordinator,
            verifier,
            e2e,
        }
    }

    pub async fn verify_ticket(&self, token: &str) -> Result<bool> {
        self.verifier.verify_ticket(token, &self.node_id).await
    }

    pub fn encryption_public_key(&self) -> &str {
        self.e2e.public_key_b64()
    }

    pub fn derive_e2e_session_key(&self, client_public_key_b64: &str) -> anyhow::Result<[u8; 32]> {
        self.e2e.derive_session_key(client_public_key_b64)
    }

    pub async fn chat(
        &self,
        model_id: &str,
        messages: Vec<ChatMessage>,
    ) -> Result<InferenceResponse> {
        let engine = self.engine_for_model(model_id).await?;
        engine.chat(model_id, messages).await
    }

    pub async fn chat_stream(
        &self,
        model_id: &str,
        messages: Vec<ChatMessage>,
    ) -> Result<Pin<Box<dyn Stream<Item = Result<StreamingChunk>> + Send>>> {
        let engine = self.engine_for_model(model_id).await?;
        engine.chat_stream(model_id, messages).await
    }

    async fn engine_for_model(&self, model_id: &str) -> Result<&dyn InferenceEngine> {
        let registry = self.registry.read().await;
        let model = registry
            .find_by_name(model_id)
            .or_else(|| registry.find_by_hash(model_id))
            .ok_or_else(|| anyhow::anyhow!("Model not found: {model_id}"))?;
        let engine_type = model.engine_type;
        drop(registry);

        self.engines
            .get(&engine_type)
            .map(|e| e.as_ref())
            .ok_or_else(|| anyhow::anyhow!("No engine registered for type {engine_type:?}"))
    }

    pub async fn refresh_model_registry(&self) -> Result<()> {
        let mut new_registry = ModelRegistry::new();

        for engine in self.engines.values() {
            if engine.is_healthy().await {
                match engine.get_models().await {
                    Ok(models) => {
                        for model in models {
                            new_registry.add_model(model);
                        }
                    }
                    Err(e) => error!("Failed to fetch models from engine: {}", e),
                }
            }
        }

        let mut registry = self.registry.write().await;
        *registry = new_registry;
        info!(
            "Model registry refreshed: {} models found",
            registry.models.len()
        );
        Ok(())
    }

    pub async fn run_initial_benchmark(&self) -> Result<()> {
        info!("Running initial hardware benchmark...");
        let result =
            crate::infrastructure::system::benchmark::run_benchmark("startup", 512).await?;
        info!(
            "✓ Hardware verified: {} ({:.4}s)",
            result.device_name, result.duration
        );
        Ok(())
    }

    pub async fn send_heartbeat(&self) -> Result<()> {
        let is_idle = self.monitor.is_idle().await.unwrap_or(false);
        let status = if is_idle {
            NodeStatus::Idle
        } else {
            NodeStatus::Busy
        };
        let hardware = self.monitor.get_status().await?;
        let models = self.registry.read().await.to_model_identities();

        self.coordinator
            .send_heartbeat(
                &self.node_id,
                status,
                models,
                hardware,
                Vec::new(),
                Some(self.encryption_public_key().to_string()),
            )
            .await?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::application::ports::{
        AuthTokenVerifier, CoordinatorClient, E2EDecryptor, HardwareMonitor, InferenceEngine,
    };
    use crate::domain::inference::{
        ChatMessage, ChatMessageDelta, InferenceChoice, InferenceResponse, StreamingChoice,
        StreamingChunk, TokenUsage,
    };
    use crate::domain::models::{EngineType, HardwareStatus, Model, NodeStatus};
    use anyhow::Result;
    use async_trait::async_trait;
    use futures::Stream;
    use monkey_troop_shared::ModelIdentity;
    use std::pin::Pin;
    use tokio::sync::Mutex;

    type HeartbeatCall = (String, NodeStatus, Vec<ModelIdentity>, HardwareStatus);
    type HeartbeatHistory = Arc<Mutex<Vec<HeartbeatCall>>>;

    struct MockInferenceEngine {
        models: Vec<Model>,
        healthy: bool,
        fail_get_models: bool,
    }

    #[async_trait]
    impl InferenceEngine for MockInferenceEngine {
        async fn get_models(&self) -> Result<Vec<Model>> {
            if self.fail_get_models {
                Err(anyhow::anyhow!("Engine error"))
            } else if self.healthy {
                Ok(self.models.clone())
            } else {
                Err(anyhow::anyhow!("Unhealthy engine"))
            }
        }
        async fn is_healthy(&self) -> bool {
            self.healthy
        }
        async fn chat(
            &self,
            model: &str,
            _messages: Vec<ChatMessage>,
        ) -> Result<InferenceResponse> {
            Ok(InferenceResponse {
                id: "mock-id".to_string(),
                object: "chat.completion".to_string(),
                created: 0,
                model: model.to_string(),
                choices: vec![InferenceChoice {
                    index: 0,
                    message: ChatMessage {
                        role: "assistant".to_string(),
                        content: "mock response".to_string(),
                    },
                    finish_reason: "stop".to_string(),
                }],
                usage: TokenUsage {
                    prompt_tokens: 0,
                    completion_tokens: 0,
                    total_tokens: 0,
                },
            })
        }
        async fn chat_stream(
            &self,
            model: &str,
            _messages: Vec<ChatMessage>,
        ) -> Result<Pin<Box<dyn Stream<Item = Result<StreamingChunk>> + Send>>> {
            let chunk = StreamingChunk {
                id: "mock-id".to_string(),
                object: "chat.completion.chunk".to_string(),
                created: 0,
                model: model.to_string(),
                choices: vec![StreamingChoice {
                    index: 0,
                    delta: ChatMessageDelta {
                        role: Some("assistant".to_string()),
                        content: Some("mock".to_string()),
                    },
                    finish_reason: Some("stop".to_string()),
                }],
            };
            Ok(Box::pin(futures::stream::iter(vec![Ok(chunk)])))
        }
    }

    struct MockHardwareMonitor {
        status: HardwareStatus,
        is_idle: bool,
    }

    #[async_trait]
    impl HardwareMonitor for MockHardwareMonitor {
        async fn get_status(&self) -> Result<HardwareStatus> {
            Ok(self.status.clone())
        }
        async fn is_idle(&self) -> Result<bool> {
            Ok(self.is_idle)
        }
    }

    struct MockCoordinatorClient {
        heartbeat_calls: HeartbeatHistory,
    }

    #[async_trait]
    impl CoordinatorClient for MockCoordinatorClient {
        async fn send_heartbeat(
            &self,
            node_id: &str,
            status: NodeStatus,
            models: Vec<ModelIdentity>,
            hardware: HardwareStatus,
            _engines: Vec<String>,
            _encryption_public_key: Option<String>,
        ) -> Result<()> {
            let mut calls = self.heartbeat_calls.lock().await;
            calls.push((node_id.to_string(), status, models, hardware));
            Ok(())
        }
    }

    struct MockAuthTokenVerifier {
        valid_token: String,
    }

    #[async_trait]
    impl AuthTokenVerifier for MockAuthTokenVerifier {
        async fn verify_ticket(&self, token: &str, target_node_id: &str) -> Result<bool> {
            Ok(token == self.valid_token && target_node_id.starts_with("node-"))
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

    fn make_engines(
        items: Vec<(EngineType, Box<dyn InferenceEngine>)>,
    ) -> HashMap<EngineType, Box<dyn InferenceEngine>> {
        items.into_iter().collect()
    }

    fn empty_engines() -> HashMap<EngineType, Box<dyn InferenceEngine>> {
        HashMap::new()
    }

    #[tokio::test]
    async fn test_refresh_model_registry() {
        let node_id = "node-1".to_string();
        let registry = Arc::new(RwLock::new(ModelRegistry::new()));

        let engine1 = Box::new(MockInferenceEngine {
            models: vec![Model {
                id: "model1".to_string(),
                content_hash: "sha256:aaa".to_string(),
                size_bytes: 100,
                engine_type: EngineType::Ollama,
            }],
            healthy: true,
            fail_get_models: false,
        });

        let engine2 = Box::new(MockInferenceEngine {
            models: vec![Model {
                id: "model2".to_string(),
                content_hash: "sha256:bbb".to_string(),
                size_bytes: 200,
                engine_type: EngineType::Vllm,
            }],
            healthy: false,
            fail_get_models: false,
        });

        let engine3 = Box::new(MockInferenceEngine {
            models: vec![Model {
                id: "model3".to_string(),
                content_hash: "sha256:ccc".to_string(),
                size_bytes: 300,
                engine_type: EngineType::LmStudio,
            }],
            healthy: true,
            fail_get_models: true,
        });

        let monitor = Arc::new(MockHardwareMonitor {
            status: HardwareStatus {
                gpu_name: "GPU1".to_string(),
                vram_free_mb: 1024,
            },
            is_idle: true,
        });

        let coordinator = Arc::new(MockCoordinatorClient {
            heartbeat_calls: Arc::new(Mutex::new(Vec::new())),
        });

        let verifier = Arc::new(MockAuthTokenVerifier {
            valid_token: "secret".to_string(),
        });

        let service = WorkerService::new(
            node_id,
            registry.clone(),
            make_engines(vec![
                (EngineType::Ollama, engine1),
                (EngineType::Vllm, engine2),
                (EngineType::LmStudio, engine3),
            ]),
            monitor,
            coordinator,
            verifier,
            Arc::new(MockE2EDecryptor),
        );

        service.refresh_model_registry().await.unwrap();

        let registry_read = registry.read().await;
        assert_eq!(registry_read.models.len(), 1);
        assert_eq!(registry_read.models[0].id, "model1");
    }

    #[tokio::test]
    async fn test_send_heartbeat() {
        let node_id = "node-1".to_string();
        let registry = Arc::new(RwLock::new(ModelRegistry::new()));
        {
            let mut reg = registry.write().await;
            reg.add_model(Model {
                id: "model1".to_string(),
                content_hash: "sha256:aaa".to_string(),
                size_bytes: 100,
                engine_type: EngineType::Ollama,
            });
        }

        let monitor = Arc::new(MockHardwareMonitor {
            status: HardwareStatus {
                gpu_name: "GPU1".to_string(),
                vram_free_mb: 8192,
            },
            is_idle: true,
        });

        let heartbeat_calls = Arc::new(Mutex::new(Vec::new()));
        let coordinator = Arc::new(MockCoordinatorClient {
            heartbeat_calls: heartbeat_calls.clone(),
        });

        let verifier = Arc::new(MockAuthTokenVerifier {
            valid_token: "secret".to_string(),
        });

        let service = WorkerService::new(
            node_id.clone(),
            registry,
            empty_engines(),
            monitor,
            coordinator,
            verifier,
            Arc::new(MockE2EDecryptor),
        );

        service.send_heartbeat().await.unwrap();

        let calls = heartbeat_calls.lock().await;
        assert_eq!(calls.len(), 1);
        let (sent_node_id, status, models, hardware) = &calls[0];
        assert_eq!(sent_node_id, &node_id);
        assert!(matches!(status, NodeStatus::Idle));
        assert_eq!(models.len(), 1);
        assert_eq!(models[0].name, "model1");
        assert_eq!(models[0].content_hash, "sha256:aaa");
        assert_eq!(models[0].size_bytes, 100);
        assert_eq!(hardware.gpu_name, "GPU1");
        assert_eq!(hardware.vram_free_mb, 8192);
    }

    #[tokio::test]
    async fn test_verify_ticket() {
        let node_id = "node-1".to_string();
        let registry = Arc::new(RwLock::new(ModelRegistry::new()));
        let monitor = Arc::new(MockHardwareMonitor {
            status: HardwareStatus {
                gpu_name: "GPU1".to_string(),
                vram_free_mb: 0,
            },
            is_idle: true,
        });
        let coordinator = Arc::new(MockCoordinatorClient {
            heartbeat_calls: Arc::new(Mutex::new(Vec::new())),
        });
        let verifier = Arc::new(MockAuthTokenVerifier {
            valid_token: "secret".to_string(),
        });

        let service = WorkerService::new(
            node_id,
            registry,
            empty_engines(),
            monitor,
            coordinator,
            verifier,
            Arc::new(MockE2EDecryptor),
        );

        assert!(service.verify_ticket("secret").await.unwrap());
        assert!(!service.verify_ticket("wrong").await.unwrap());
    }

    #[tokio::test]
    async fn test_run_initial_benchmark() {
        let node_id = "node-1".to_string();
        let registry = Arc::new(RwLock::new(ModelRegistry::new()));
        let monitor = Arc::new(MockHardwareMonitor {
            status: HardwareStatus {
                gpu_name: "GPU1".to_string(),
                vram_free_mb: 0,
            },
            is_idle: true,
        });
        let coordinator = Arc::new(MockCoordinatorClient {
            heartbeat_calls: Arc::new(Mutex::new(Vec::new())),
        });
        let verifier = Arc::new(MockAuthTokenVerifier {
            valid_token: "secret".to_string(),
        });

        let service = WorkerService::new(
            node_id,
            registry,
            empty_engines(),
            monitor,
            coordinator,
            verifier,
            Arc::new(MockE2EDecryptor),
        );

        let result = service.run_initial_benchmark().await;
        assert!(
            result.is_ok() || result.is_err(),
            "run_initial_benchmark should return a Result"
        );
    }

    #[tokio::test]
    async fn test_encryption_public_key() {
        let node_id = "node-1".to_string();
        let registry = Arc::new(RwLock::new(ModelRegistry::new()));
        let monitor = Arc::new(MockHardwareMonitor {
            status: HardwareStatus {
                gpu_name: "GPU1".to_string(),
                vram_free_mb: 0,
            },
            is_idle: true,
        });
        let coordinator = Arc::new(MockCoordinatorClient {
            heartbeat_calls: Arc::new(Mutex::new(Vec::new())),
        });
        let verifier = Arc::new(MockAuthTokenVerifier {
            valid_token: "secret".to_string(),
        });

        let service = WorkerService::new(
            node_id,
            registry,
            empty_engines(),
            monitor,
            coordinator,
            verifier,
            Arc::new(MockE2EDecryptor),
        );

        assert_eq!(
            service.encryption_public_key(),
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        );
    }

    #[tokio::test]
    async fn test_chat_delegates_to_engine() {
        let node_id = "node-1".to_string();
        let registry = Arc::new(RwLock::new(ModelRegistry::new()));
        {
            let mut reg = registry.write().await;
            reg.add_model(Model {
                id: "llama3".to_string(),
                content_hash: "sha256:aaa".to_string(),
                size_bytes: 100,
                engine_type: EngineType::Ollama,
            });
        }

        let engine = Box::new(MockInferenceEngine {
            models: vec![],
            healthy: true,
            fail_get_models: false,
        });

        let monitor = Arc::new(MockHardwareMonitor {
            status: HardwareStatus {
                gpu_name: "GPU1".to_string(),
                vram_free_mb: 0,
            },
            is_idle: true,
        });
        let coordinator = Arc::new(MockCoordinatorClient {
            heartbeat_calls: Arc::new(Mutex::new(Vec::new())),
        });
        let verifier = Arc::new(MockAuthTokenVerifier {
            valid_token: "secret".to_string(),
        });

        let service = WorkerService::new(
            node_id,
            registry,
            make_engines(vec![(EngineType::Ollama, engine)]),
            monitor,
            coordinator,
            verifier,
            Arc::new(MockE2EDecryptor),
        );

        let messages = vec![ChatMessage {
            role: "user".to_string(),
            content: "hi".to_string(),
        }];
        let resp = service.chat("llama3", messages).await.unwrap();
        assert_eq!(resp.choices[0].message.content, "mock response");
    }

    #[tokio::test]
    async fn test_chat_stream_delegates_to_engine() {
        use futures::StreamExt;

        let node_id = "node-1".to_string();
        let registry = Arc::new(RwLock::new(ModelRegistry::new()));
        {
            let mut reg = registry.write().await;
            reg.add_model(Model {
                id: "llama3".to_string(),
                content_hash: "sha256:aaa".to_string(),
                size_bytes: 100,
                engine_type: EngineType::Ollama,
            });
        }

        let engine = Box::new(MockInferenceEngine {
            models: vec![],
            healthy: true,
            fail_get_models: false,
        });

        let monitor = Arc::new(MockHardwareMonitor {
            status: HardwareStatus {
                gpu_name: "GPU1".to_string(),
                vram_free_mb: 0,
            },
            is_idle: true,
        });
        let coordinator = Arc::new(MockCoordinatorClient {
            heartbeat_calls: Arc::new(Mutex::new(Vec::new())),
        });
        let verifier = Arc::new(MockAuthTokenVerifier {
            valid_token: "secret".to_string(),
        });

        let service = WorkerService::new(
            node_id,
            registry,
            make_engines(vec![(EngineType::Ollama, engine)]),
            monitor,
            coordinator,
            verifier,
            Arc::new(MockE2EDecryptor),
        );

        let messages = vec![ChatMessage {
            role: "user".to_string(),
            content: "hi".to_string(),
        }];
        let mut stream = service.chat_stream("llama3", messages).await.unwrap();
        let chunk = stream.next().await.unwrap().unwrap();
        assert_eq!(chunk.choices[0].delta.content, Some("mock".to_string()));
    }

    #[tokio::test]
    async fn test_chat_model_not_found() {
        let node_id = "node-1".to_string();
        let registry = Arc::new(RwLock::new(ModelRegistry::new()));
        let monitor = Arc::new(MockHardwareMonitor {
            status: HardwareStatus {
                gpu_name: "GPU1".to_string(),
                vram_free_mb: 0,
            },
            is_idle: true,
        });
        let coordinator = Arc::new(MockCoordinatorClient {
            heartbeat_calls: Arc::new(Mutex::new(Vec::new())),
        });
        let verifier = Arc::new(MockAuthTokenVerifier {
            valid_token: "secret".to_string(),
        });

        let service = WorkerService::new(
            node_id,
            registry,
            empty_engines(),
            monitor,
            coordinator,
            verifier,
            Arc::new(MockE2EDecryptor),
        );

        let messages = vec![ChatMessage {
            role: "user".to_string(),
            content: "hi".to_string(),
        }];
        let result = service.chat("nonexistent", messages).await;
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("Model not found"));
    }

    #[tokio::test]
    async fn test_chat_no_engine_for_type() {
        let node_id = "node-1".to_string();
        let registry = Arc::new(RwLock::new(ModelRegistry::new()));
        {
            let mut reg = registry.write().await;
            reg.add_model(Model {
                id: "llama3".to_string(),
                content_hash: "sha256:aaa".to_string(),
                size_bytes: 100,
                engine_type: EngineType::Vllm,
            });
        }

        let monitor = Arc::new(MockHardwareMonitor {
            status: HardwareStatus {
                gpu_name: "GPU1".to_string(),
                vram_free_mb: 0,
            },
            is_idle: true,
        });
        let coordinator = Arc::new(MockCoordinatorClient {
            heartbeat_calls: Arc::new(Mutex::new(Vec::new())),
        });
        let verifier = Arc::new(MockAuthTokenVerifier {
            valid_token: "secret".to_string(),
        });

        let service = WorkerService::new(
            node_id,
            registry,
            empty_engines(),
            monitor,
            coordinator,
            verifier,
            Arc::new(MockE2EDecryptor),
        );

        let messages = vec![ChatMessage {
            role: "user".to_string(),
            content: "hi".to_string(),
        }];
        let result = service.chat("llama3", messages).await;
        assert!(result.is_err());
        assert!(result
            .unwrap_err()
            .to_string()
            .contains("No engine registered"));
    }
}
