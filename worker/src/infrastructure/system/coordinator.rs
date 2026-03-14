use crate::application::ports::CoordinatorClient;
use crate::domain::models::{HardwareStatus, NodeStatus};
use anyhow::Result;
use async_trait::async_trait;
use reqwest::Client;
use serde_json::json;

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
        models: Vec<String>,
        hardware: HardwareStatus,
    ) -> Result<()> {
        let endpoint = format!("{}/heartbeat", self.base_url);

        let payload = json!({
            "node_id": node_id,
            "status": format!("{status:?}").to_uppercase(),
            "models": models,
            "hardware": {
                "gpu": hardware.gpu_name,
                "vram_free": hardware.vram_free_mb
            },
            "tailscale_ip": "100.64.0.1", // Placeholder, should be resolved from system
            "engines": [] // To be populated
        });

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
            .send_heartbeat("node-1", NodeStatus::Idle, vec!["llama3".to_string()], hardware)
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
            .send_heartbeat("node-1", NodeStatus::Idle, vec!["llama3".to_string()], hardware)
            .await;

        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("500"));
    }
}
