use crate::domain::models::{HardwareStatus, Model, NodeStatus};
use anyhow::Result;
use async_trait::async_trait;

#[async_trait]
pub trait InferenceEngine: Send + Sync {
    async fn get_models(&self) -> Result<Vec<Model>>;
    async fn is_healthy(&self) -> bool;
}

#[async_trait]
pub trait HardwareMonitor: Send + Sync {
    async fn get_status(&self) -> Result<HardwareStatus>;
    async fn is_idle(&self) -> Result<bool>;
}

#[async_trait]
pub trait CoordinatorClient: Send + Sync {
    async fn send_heartbeat(
        &self,
        node_id: &str,
        status: NodeStatus,
        models: Vec<String>,
        hardware: HardwareStatus,
    ) -> Result<()>;
}

#[async_trait]
pub trait AuthTokenVerifier: Send + Sync {
    async fn verify_ticket(&self, token: &str, target_node_id: &str) -> Result<bool>;
}
