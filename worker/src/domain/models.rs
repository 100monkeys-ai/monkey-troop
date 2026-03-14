use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Model {
    pub id: String,
    pub engine_type: EngineType,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum EngineType {
    Ollama,
    Vllm,
    LmStudio,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareStatus {
    pub gpu_name: String,
    pub vram_free_mb: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NodeStatus {
    Idle,
    Busy,
    Offline,
}

pub struct ModelRegistry {
    pub models: Vec<Model>,
}

impl ModelRegistry {
    pub fn new() -> Self {
        Self { models: Vec::new() }
    }

    pub fn add_model(&mut self, model: Model) {
        if !self.models.iter().any(|m| m.id == model.id) {
            self.models.push(model);
        }
    }

    pub fn get_model_ids(&self) -> Vec<String> {
        self.models.iter().map(|m| m.id.clone()).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_model_registry_new() {
        let registry = ModelRegistry::new();
        assert!(registry.models.is_empty());
    }

    #[test]
    fn test_model_registry_add_model() {
        let mut registry = ModelRegistry::new();
        let model = Model {
            id: "test-model".to_string(),
            engine_type: EngineType::Ollama,
        };

        registry.add_model(model.clone());
        assert_eq!(registry.models.len(), 1);
        assert_eq!(registry.models[0].id, "test-model");

        // Test duplicate prevention
        registry.add_model(model);
        assert_eq!(registry.models.len(), 1);
    }

    #[test]
    fn test_model_registry_get_model_ids() {
        let mut registry = ModelRegistry::new();
        registry.add_model(Model {
            id: "model1".to_string(),
            engine_type: EngineType::Ollama,
        });
        registry.add_model(Model {
            id: "model2".to_string(),
            engine_type: EngineType::Vllm,
        });

        let ids = registry.get_model_ids();
        assert_eq!(ids.len(), 2);
        assert!(ids.contains(&"model1".to_string()));
        assert!(ids.contains(&"model2".to_string()));
    }
}
