use crate::application::ports::InferenceEngine;
use crate::domain::models::{EngineType, Model};
use anyhow::Result;
use async_trait::async_trait;
use serde::Deserialize;
use std::env;

#[derive(Deserialize)]
struct OllamaModels {
    models: Vec<OllamaModel>,
}

#[derive(Deserialize)]
struct OllamaModel {
    name: String,
}

pub struct OllamaEngine {
    base_url: String,
    client: reqwest::Client,
}

impl OllamaEngine {
    pub fn new() -> Self {
        let base_url =
            env::var("OLLAMA_HOST").unwrap_or_else(|_| "http://localhost:11434".to_string());
        Self {
            base_url,
            client: reqwest::Client::new(),
        }
    }
}

#[async_trait]
impl InferenceEngine for OllamaEngine {
    async fn get_models(&self) -> Result<Vec<Model>> {
        let response = self
            .client
            .get(format!("{}/api/tags", self.base_url))
            .send()
            .await?;

        let models_info: OllamaModels = response.json().await?;

        Ok(models_info
            .models
            .into_iter()
            .map(|m| Model {
                id: m.name,
                engine_type: EngineType::Ollama,
            })
            .collect())
    }

    async fn is_healthy(&self) -> bool {
        let response = self
            .client
            .get(format!("{}/api/version", self.base_url))
            .timeout(std::time::Duration::from_secs(2))
            .send()
            .await;

        match response {
            Ok(resp) => resp.status().is_success(),
            Err(_) => false,
        }
    }
}
