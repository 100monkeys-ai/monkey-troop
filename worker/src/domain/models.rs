use monkey_troop_shared::ModelIdentity;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Model {
    pub id: String,
    pub content_hash: String,
    pub size_bytes: u64,
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
        if !self
            .models
            .iter()
            .any(|m| m.content_hash == model.content_hash)
        {
            self.models.push(model);
        }
    }

    pub fn find_by_name(&self, name: &str) -> Option<&Model> {
        self.models.iter().find(|m| m.id == name)
    }

    pub fn find_by_hash(&self, hash: &str) -> Option<&Model> {
        self.models.iter().find(|m| m.content_hash == hash)
    }

    pub fn to_model_identities(&self) -> Vec<ModelIdentity> {
        self.models
            .iter()
            .map(|m| ModelIdentity {
                name: m.id.clone(),
                content_hash: m.content_hash.clone(),
                size_bytes: m.size_bytes,
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_model(id: &str, hash: &str, size: u64, engine: EngineType) -> Model {
        Model {
            id: id.to_string(),
            content_hash: hash.to_string(),
            size_bytes: size,
            engine_type: engine,
        }
    }

    #[test]
    fn test_model_registry_new() {
        let registry = ModelRegistry::new();
        assert!(registry.models.is_empty());
    }

    #[test]
    fn test_model_registry_add_model() {
        let mut registry = ModelRegistry::new();
        let model = make_model("test-model", "sha256:abc123", 1024, EngineType::Ollama);

        registry.add_model(model.clone());
        assert_eq!(registry.models.len(), 1);
        assert_eq!(registry.models[0].id, "test-model");

        // Test duplicate prevention by content_hash
        registry.add_model(model);
        assert_eq!(registry.models.len(), 1);
    }

    #[test]
    fn test_model_registry_dedup_by_hash() {
        let mut registry = ModelRegistry::new();
        // Same hash, different name — should be treated as duplicate
        registry.add_model(make_model("name-a", "sha256:same", 100, EngineType::Ollama));
        registry.add_model(make_model("name-b", "sha256:same", 100, EngineType::Vllm));
        assert_eq!(registry.models.len(), 1);
        assert_eq!(registry.models[0].id, "name-a");
    }

    #[test]
    fn test_find_by_name() {
        let mut registry = ModelRegistry::new();
        registry.add_model(make_model("llama3", "sha256:abc", 500, EngineType::Ollama));

        assert!(registry.find_by_name("llama3").is_some());
        assert_eq!(
            registry.find_by_name("llama3").unwrap().content_hash,
            "sha256:abc"
        );
        assert!(registry.find_by_name("nonexistent").is_none());
    }

    #[test]
    fn test_find_by_hash() {
        let mut registry = ModelRegistry::new();
        registry.add_model(make_model("llama3", "sha256:abc", 500, EngineType::Ollama));

        assert!(registry.find_by_hash("sha256:abc").is_some());
        assert_eq!(registry.find_by_hash("sha256:abc").unwrap().id, "llama3");
        assert!(registry.find_by_hash("sha256:zzz").is_none());
    }

    #[test]
    fn test_to_model_identities() {
        let mut registry = ModelRegistry::new();
        registry.add_model(make_model("model1", "sha256:aaa", 100, EngineType::Ollama));
        registry.add_model(make_model("model2", "sha256:bbb", 200, EngineType::Vllm));

        let identities = registry.to_model_identities();
        assert_eq!(identities.len(), 2);
        assert_eq!(identities[0].name, "model1");
        assert_eq!(identities[0].content_hash, "sha256:aaa");
        assert_eq!(identities[0].size_bytes, 100);
        assert_eq!(identities[1].name, "model2");
        assert_eq!(identities[1].content_hash, "sha256:bbb");
        assert_eq!(identities[1].size_bytes, 200);
    }
}
