use super::EngineDriver;
use anyhow::Result;
use monkey_troop_shared::EngineInfo;
use serde::Deserialize;

#[derive(Deserialize)]
struct LMStudioModel {
    id: String,
}

#[derive(Deserialize)]
struct LMStudioModels {
    data: Vec<LMStudioModel>,
}

pub struct LMStudioDriver {
    base_url: String,
}

impl LMStudioDriver {
    pub fn new() -> Self {
        Self {
            base_url: "http://localhost:1234".to_string(),
        }
    }
}

impl EngineDriver for LMStudioDriver {
    fn detect(&self) -> Result<bool> {
        let client = reqwest::blocking::Client::new();
        let response = client
            .get(&format!("{}/v1/models", self.base_url))
            .timeout(std::time::Duration::from_secs(2))
            .send();
        
        Ok(response.is_ok())
    }
    
    fn get_info(&self) -> Result<EngineInfo> {
        Ok(EngineInfo {
            engine_type: "lmstudio".to_string(),
            version: "unknown".to_string(),
            port: 1234,
        })
    }
    
    fn get_models(&self) -> Result<Vec<String>> {
        let client = reqwest::blocking::Client::new();
        let response = client
            .get(&format!("{}/v1/models", self.base_url))
            .send()?;
        
        let models_info: LMStudioModels = response.json()?;
        
        Ok(models_info.data.into_iter().map(|m| m.id).collect())
    }
}
