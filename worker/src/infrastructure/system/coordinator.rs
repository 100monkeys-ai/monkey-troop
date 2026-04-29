use crate::application::ports::CoordinatorClient;
use crate::domain::models::{HardwareStatus, NodeStatus};
use anyhow::Result;
use async_trait::async_trait;
use monkey_troop_shared::ModelIdentity;
use reqwest::Client;
use serde_json::json;
use std::env;

fn resolve_tailscale_ip() -> Option<String> {
    env::var("TAILSCALE_IP").ok()
}

pub struct HttpCoordinatorClient {
    base_url: String,
    client: Client,
}

impl HttpCoordinatorClient {
    pub fn new(base_url: String) -> Self {
        Self {
            base_url,
            client: Client::new(),
        }
    }
}

#[async_trait]
impl CoordinatorClient for HttpCoordinatorClient {
    async fn send_heartbeat(
        &self,
        node_id: &str,
        status: NodeStatus,
        models: Vec<ModelIdentity>,
        hardware: HardwareStatus,
        engines: Vec<String>,
        encryption_public_key: Option<String>,
    ) -> Result<()> {
        let endpoint = format!("{}/heartbeat", self.base_url);

        let mut payload = json!({
            "node_id": node_id,
            "status": format!("{status:?}").to_uppercase(),
            "models": models,
            "hardware": {
                "gpu": hardware.gpu_name,
                "vram_free": hardware.vram_free_mb
            },
            "tailscale_ip": resolve_tailscale_ip(),
            "engines": engines
        });

        if let (Some(key), Some(obj)) = (encryption_public_key, payload.as_object_mut()) {
            obj.insert(
                "encryption_public_key".to_string(),
                serde_json::Value::String(key),
            );
        }

        let response = self.client.post(endpoint).json(&payload).send().await?;

        if response.status().is_success() {
            Ok(())
        } else {
            anyhow::bail!("Heartbeat failed with status: {}", response.status())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use httpmock::prelude::*;

    fn test_model_identities() -> Vec<ModelIdentity> {
        vec![ModelIdentity {
            name: "llama3".to_string(),
            content_hash: "sha256:abc123".to_string(),
            size_bytes: 4_000_000_000,
        }]
    }

    #[tokio::test]
    async fn test_send_heartbeat_success() {
        let server = MockServer::start();
        let coordinator = HttpCoordinatorClient::new(server.base_url());

        let _mock = server.mock(|when, then| {
            when.method(POST).path("/heartbeat");
            then.status(200);
        });

        let hardware = HardwareStatus {
            gpu_name: "RTX 4090".to_string(),
            vram_free_mb: 24576,
        };

        let result = coordinator
            .send_heartbeat(
                "node-1",
                NodeStatus::Idle,
                test_model_identities(),
                hardware,
                Vec::new(),
                None,
            )
            .await;

        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_send_heartbeat_with_encryption_key() {
        let server = MockServer::start();
        let coordinator = HttpCoordinatorClient::new(server.base_url());

        let _mock = server.mock(|when, then| {
            when.method(POST).path("/heartbeat");
            then.status(200);
        });

        let hardware = HardwareStatus {
            gpu_name: "RTX 4090".to_string(),
            vram_free_mb: 24576,
        };

        let result = coordinator
            .send_heartbeat(
                "node-1",
                NodeStatus::Idle,
                test_model_identities(),
                hardware,
                Vec::new(),
                Some("test-public-key-b64".to_string()),
            )
            .await;

        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_send_heartbeat_failure() {
        let server = MockServer::start();
        let coordinator = HttpCoordinatorClient::new(server.base_url());

        let _mock = server.mock(|when, then| {
            when.method(POST).path("/heartbeat");
            then.status(500);
        });

        let hardware = HardwareStatus {
            gpu_name: "RTX 4090".to_string(),
            vram_free_mb: 24576,
        };

        let result = coordinator
            .send_heartbeat(
                "node-1",
                NodeStatus::Idle,
                test_model_identities(),
                hardware,
                Vec::new(),
                None,
            )
            .await;

        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("500"));
    }
}
