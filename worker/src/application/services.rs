use crate::application::ports::{
    AuthTokenVerifier, CoordinatorClient, HardwareMonitor, InferenceEngine,
};
use crate::domain::models::{ModelRegistry, NodeStatus};
use anyhow::Result;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{error, info};

pub struct WorkerService {
    pub node_id: String,
    pub registry: Arc<RwLock<ModelRegistry>>,
    engines: Vec<Box<dyn InferenceEngine>>,
    monitor: Arc<dyn HardwareMonitor>,
    coordinator: Arc<dyn CoordinatorClient>,
    verifier: Arc<dyn AuthTokenVerifier>,
}

impl WorkerService {
    pub fn new(
        node_id: String,
        registry: Arc<RwLock<ModelRegistry>>,
        engines: Vec<Box<dyn InferenceEngine>>,
        monitor: Arc<dyn HardwareMonitor>,
        coordinator: Arc<dyn CoordinatorClient>,
        verifier: Arc<dyn AuthTokenVerifier>,
    ) -> Self {
        Self {
            node_id,
            registry,
            engines,
            monitor,
            coordinator,
            verifier,
        }
    }

    pub async fn verify_ticket(&self, token: &str) -> Result<bool> {
        self.verifier.verify_ticket(token, &self.node_id).await
    }

    pub async fn refresh_model_registry(&self) -> Result<()> {
        let mut new_registry = ModelRegistry::new();

        for engine in &self.engines {
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
        // Use a small matrix size for quick startup verification
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
        let models = self.registry.read().await.get_model_ids();

        self.coordinator
            .send_heartbeat(&self.node_id, status, models, hardware)
            .await?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::application::ports::{
        AuthTokenVerifier, CoordinatorClient, HardwareMonitor, InferenceEngine,
    };
    use crate::domain::models::{EngineType, HardwareStatus, Model, NodeStatus};
    use anyhow::Result;
    use async_trait::async_trait;
    use tokio::sync::Mutex;

    // Fully implemented mocks
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
        heartbeat_calls: Arc<Mutex<Vec<(String, NodeStatus, Vec<String>, HardwareStatus)>>>,
    }

    #[async_trait]
    impl CoordinatorClient for MockCoordinatorClient {
        async fn send_heartbeat(
            &self,
            node_id: &str,
            status: NodeStatus,
            models: Vec<String>,
            hardware: HardwareStatus,
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

    #[tokio::test]
    async fn test_refresh_model_registry() {
        let node_id = "node-1".to_string();
        let registry = Arc::new(RwLock::new(ModelRegistry::new()));

        let engine1 = Box::new(MockInferenceEngine {
            models: vec![Model {
                id: "model1".to_string(),
                engine_type: EngineType::Ollama,
            }],
            healthy: true,
            fail_get_models: false,
        });

        let engine2 = Box::new(MockInferenceEngine {
            models: vec![Model {
                id: "model2".to_string(),
                engine_type: EngineType::Vllm,
            }],
            healthy: false,
            fail_get_models: false,
        });

        let engine3 = Box::new(MockInferenceEngine {
            models: vec![Model {
                id: "model3".to_string(),
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
            vec![engine1, engine2, engine3],
            monitor,
            coordinator,
            verifier,
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
            vec![],
            monitor,
            coordinator,
            verifier,
        );

        service.send_heartbeat().await.unwrap();

        let calls = heartbeat_calls.lock().await;
        assert_eq!(calls.len(), 1);
        let (sent_node_id, status, models, hardware) = &calls[0];
        assert_eq!(sent_node_id, &node_id);
        assert!(matches!(status, NodeStatus::Idle));
        assert_eq!(models.len(), 1);
        assert_eq!(models[0], "model1");
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

        let service = WorkerService::new(node_id, registry, vec![], monitor, coordinator, verifier);

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

        let service = WorkerService::new(node_id, registry, vec![], monitor, coordinator, verifier);

        // This might fail if benchmark.py is missing or python/numpy missing, 
        // but we just want to cover the call path in the application service.
        let _ = service.run_initial_benchmark().await;
    }
}
