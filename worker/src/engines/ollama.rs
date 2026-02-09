use super::EngineDriver;
use anyhow::Result;
use monkey_troop_shared::EngineInfo;
use serde::Deserialize;
use std::env;

#[derive(Deserialize)]
struct OllamaVersion {
    version: String,
}

#[derive(Deserialize)]
struct OllamaModels {
    models: Vec<OllamaModel>,
}

#[derive(Deserialize)]
struct OllamaModel {
    name: String,
}

pub struct OllamaDriver {
    base_url: String,
}

impl OllamaDriver {
    pub fn new() -> Self {
        let base_url = env::var("OLLAMA_HOST")
            .unwrap_or_else(|_| "http://localhost:11434".to_string());
        
        Self { base_url }
    }
}

impl EngineDriver for OllamaDriver {
    fn detect(&self) -> Result<bool> {
        // Try to hit the version endpoint
        let client = reqwest::blocking::Client::new();
        let response = client
            .get(&format!("{}/api/version", self.base_url))
            .timeout(std::time::Duration::from_secs(2))
            .send();
        
        Ok(response.is_ok())
    }
    
    fn get_info(&self) -> Result<EngineInfo> {
        let client = reqwest::blocking::Client::new();
        let response = client
            .get(&format!("{}/api/version", self.base_url))
            .send()?;
        
        let version_info: OllamaVersion = response.json()?;
        
        Ok(EngineInfo {
            engine_type: "ollama".to_string(),
            version: version_info.version,
            port: 11434, // Default Ollama port
        })
    }
    
    fn get_models(&self) -> Result<Vec<String>> {
        let client = reqwest::blocking::Client::new();
        let response = client
            .get(&format!("{}/api/tags", self.base_url))
            .send()?;
        
        let models_info: OllamaModels = response.json()?;
        
        Ok(models_info.models.into_iter().map(|m| m.name).collect())
    }
    
    fn get_base_url(&self) -> String {
        self.base_url.clone()
    }
}
