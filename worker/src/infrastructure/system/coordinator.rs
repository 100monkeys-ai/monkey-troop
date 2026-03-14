use async_trait::async_trait;
use crate::application::ports::CoordinatorClient;
use crate::domain::models::{NodeStatus, HardwareStatus};
use anyhow::Result;
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
        hardware: HardwareStatus
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

        let response = self.client
            .post(endpoint)
            .json(&payload)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            anyhow::bail!("Heartbeat failed with status: {}", response.status())
        }
    }
}
