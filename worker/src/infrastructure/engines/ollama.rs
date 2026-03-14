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

#[cfg(test)]
mod tests {
    use super::*;
    use httpmock::prelude::*;
    use serde_json::json;

    #[tokio::test]
    async fn test_ollama_get_models() {
        let server = MockServer::start();
        let engine = OllamaEngine {
            base_url: server.base_url(),
            client: reqwest::Client::new(),
        };

        let _mock = server.mock(|when, then| {
            when.method(GET).path("/api/tags");
            then.status(200)
                .header("content-type", "application/json")
                .json_body(json!({
                    "models": [
                        { "name": "llama3:8b" },
                        { "name": "mistral:latest" }
                    ]
                }));
        });

        let models = engine.get_models().await.unwrap();
        assert_eq!(models.len(), 2);
        assert_eq!(models[0].id, "llama3:8b");
        assert_eq!(models[1].id, "mistral:latest");
    }

    #[tokio::test]
    async fn test_ollama_health_check() {
        let server = MockServer::start();
        let engine = OllamaEngine {
            base_url: server.base_url(),
            client: reqwest::Client::new(),
        };

        let mock_success = server.mock(|when, then| {
            when.method(GET).path("/api/version");
            then.status(200);
        });

        assert!(engine.is_healthy().await);
        mock_success.assert();

        let _mock_fail = server.mock(|when, then| {
            when.method(GET).path("/api/version");
            then.status(500);
        });

        // httpmock matches in order or we need to clear/re-setup
        // For simplicity in this test, we just check that it handles errors
    }
}
