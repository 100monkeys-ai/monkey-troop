use super::EngineDriver;
use anyhow::Result;
use monkey_troop_shared::EngineInfo;
use serde::Deserialize;
use std::env;

#[derive(Deserialize)]
struct VllmModel {
    id: String,
}

#[derive(Deserialize)]
struct VllmModels {
    data: Vec<VllmModel>,
}

#[derive(Deserialize)]
struct VllmHealth {
    #[serde(default)]
    status: String,
}

pub struct VllmDriver {
    base_url: String,
}

impl VllmDriver {
    pub fn new() -> Self {
        let base_url =
            env::var("VLLM_HOST").unwrap_or_else(|_| "http://localhost:8000".to_string());

        Self { base_url }
    }
}

impl EngineDriver for VllmDriver {
    fn detect(&self) -> Result<bool> {
        let client = reqwest::blocking::Client::new();
        let response = client
            .get(format!("{}/v1/models", self.base_url))
            .timeout(std::time::Duration::from_secs(2))
            .send();

        Ok(response.is_ok())
    }

    fn get_info(&self) -> Result<EngineInfo> {
        let client = reqwest::blocking::Client::new();

        // Try to get version from /health endpoint
        let version = match client
            .get(format!("{}/health", self.base_url))
            .timeout(std::time::Duration::from_secs(2))
            .send()
        {
            Ok(response) => {
                if let Ok(health) = response.json::<VllmHealth>() {
                    if !health.status.is_empty() {
                        health.status
                    } else {
                        "unknown".to_string()
                    }
                } else {
                    "unknown".to_string()
                }
            }
            Err(_) => "unknown".to_string(),
        };

        Ok(EngineInfo {
            engine_type: "vllm".to_string(),
            version,
            port: 8000,
        })
    }

    fn get_models(&self) -> Result<Vec<String>> {
        let client = reqwest::blocking::Client::new();
        let response = client.get(format!("{}/v1/models", self.base_url)).send()?;

        let models_info: VllmModels = response.json()?;

        Ok(models_info.data.into_iter().map(|m| m.id).collect())
    }

    fn get_base_url(&self) -> String {
        self.base_url.clone()
    }
}
