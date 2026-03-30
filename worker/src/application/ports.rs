use crate::domain::models::{HardwareStatus, Model, NodeStatus};
use anyhow::Result;
use async_trait::async_trait;
use monkey_troop_shared::ModelIdentity;

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
        models: Vec<ModelIdentity>,
        hardware: HardwareStatus,
        engines: Vec<String>,
        encryption_public_key: Option<String>,
    ) -> Result<()>;
}

#[async_trait]
pub trait AuthTokenVerifier: Send + Sync {
    async fn verify_ticket(&self, token: &str, target_node_id: &str) -> Result<bool>;
}

/// Port for E2E encryption operations. Synchronous because crypto is CPU-bound and fast.
pub trait E2EDecryptor: Send + Sync {
    /// Get the base64-encoded X25519 public key for this worker
    fn public_key_b64(&self) -> &str;

    /// Derive session key from client's ephemeral public key
    fn derive_session_key(&self, client_public_key_b64: &str) -> anyhow::Result<[u8; 32]>;
}
