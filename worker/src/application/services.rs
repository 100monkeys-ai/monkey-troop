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

    pub async fn send_heartbeat(&self) -> Result<()> {
        let status = NodeStatus::Idle; // Simplified for MVP
        let hardware = self.monitor.get_status().await?;
        let models = self.registry.read().await.get_model_ids();

        self.coordinator
            .send_heartbeat(&self.node_id, status, models, hardware)
            .await?;

        Ok(())
    }
}
