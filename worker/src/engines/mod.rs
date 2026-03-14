pub mod lmstudio;
pub mod ollama;
pub mod vllm;

use anyhow::Result;
use monkey_troop_shared::EngineInfo;
use std::collections::HashMap;

/// Trait for inference engine drivers
pub trait EngineDriver {
    fn detect(&self) -> Result<bool>;
    fn get_info(&self) -> Result<EngineInfo>;
    fn get_models(&self) -> Result<Vec<String>>;
    fn get_base_url(&self) -> String;
}

/// Registry mapping model names to engine base URLs
#[derive(Debug, Clone)]
pub struct ModelRegistry {
    model_to_engine: HashMap<String, String>,
    all_models: Vec<String>,
    all_engines: Vec<EngineInfo>,
}

impl ModelRegistry {
    pub fn new() -> Self {
        Self {
            model_to_engine: HashMap::new(),
            all_models: Vec::new(),
            all_engines: Vec::new(),
        }
    }

    pub fn get_engine_url(&self, model: &str) -> Option<&String> {
        self.model_to_engine.get(model)
    }

    pub fn models(&self) -> &[String] {
        &self.all_models
    }

    pub fn engines(&self) -> &[EngineInfo] {
        &self.all_engines
    }

    pub fn is_empty(&self) -> bool {
        self.model_to_engine.is_empty()
    }
}

/// Detect all available engines concurrently
pub async fn detect_all_engines() -> Vec<Box<dyn EngineDriver + Send + Sync>> {
    let mut engines: Vec<Box<dyn EngineDriver + Send + Sync>> = Vec::new();

    // Try Ollama
    let ollama = ollama::OllamaDriver::new();
    if ollama.detect().unwrap_or(false) {
        println!("✓ Detected Ollama");
        engines.push(Box::new(ollama));
    }

    // Try vLLM
    let vllm = vllm::VllmDriver::new();
    if vllm.detect().unwrap_or(false) {
        println!("✓ Detected vLLM");
        engines.push(Box::new(vllm));
    }

    // Try LM Studio
    let lmstudio = lmstudio::LMStudioDriver::new();
    if lmstudio.detect().unwrap_or(false) {
        println!("✓ Detected LM Studio");
        engines.push(Box::new(lmstudio));
    }

    engines
}

/// Build model registry with priority: vLLM > Ollama > LM Studio
pub fn build_model_registry(
    engines: &[Box<dyn EngineDriver + Send + Sync>],
) -> Result<ModelRegistry> {
    let mut registry = ModelRegistry::new();
    let mut all_models_set = std::collections::HashSet::new();

    // Priority order: vLLM (fastest), Ollama, LM Studio
    let priority_order = ["vllm", "ollama", "lmstudio"];

    // Collect engine info
    for engine in engines {
        let info = engine.get_info()?;
        registry.all_engines.push(info);
    }

    // Build model mapping with priority
    for priority_type in &priority_order {
        for engine in engines {
            let info = engine.get_info()?;
            if info.engine_type == *priority_type {
                let models = engine.get_models()?;
                let base_url = engine.get_base_url();

                for model in models {
                    all_models_set.insert(model.clone());
                    // Only insert if not already present (priority)
                    registry
                        .model_to_engine
                        .entry(model.clone())
                        .or_insert(base_url.clone());
                }
            }
        }
    }

    // Convert set to sorted vec
    let mut all_models: Vec<String> = all_models_set.into_iter().collect();
    all_models.sort();
    registry.all_models = all_models;

    if registry.is_empty() {
        return Err(anyhow::anyhow!("No models found in any engine"));
    }

    println!(
        "📋 Registered {} models across {} engines",
        registry.all_models.len(),
        registry.all_engines.len()
    );

    Ok(registry)
}

#[cfg(test)]
mod tests {
    use super::*;

    struct MockEngine {
        engine_type: String,
        models: Vec<String>,
        base_url: String,
        version: String,
        port: u16,
    }

    impl EngineDriver for MockEngine {
        fn detect(&self) -> Result<bool> {
            Ok(true)
        }

        fn get_info(&self) -> Result<EngineInfo> {
            Ok(EngineInfo {
                engine_type: self.engine_type.clone(),
                version: self.version.clone(),
                port: self.port,
            })
        }

        fn get_models(&self) -> Result<Vec<String>> {
            Ok(self.models.clone())
        }

        fn get_base_url(&self) -> String {
            self.base_url.clone()
        }
    }

    #[test]
    fn test_build_model_registry_priority() {
        let vllm = Box::new(MockEngine {
            engine_type: "vllm".to_string(),
            models: vec!["llama-3".to_string(), "mixtral".to_string()],
            base_url: "http://localhost:8000".to_string(),
            version: "0.4.1".to_string(),
            port: 8000,
        }) as Box<dyn EngineDriver + Send + Sync>;

        let ollama = Box::new(MockEngine {
            engine_type: "ollama".to_string(),
            models: vec!["llama-3".to_string(), "phi-3".to_string()],
            base_url: "http://localhost:11434".to_string(),
            version: "0.1.33".to_string(),
            port: 11434,
        }) as Box<dyn EngineDriver + Send + Sync>;

        let lmstudio = Box::new(MockEngine {
            engine_type: "lmstudio".to_string(),
            models: vec!["llama-3".to_string(), "gemma".to_string()],
            base_url: "http://localhost:1234".to_string(),
            version: "0.2.20".to_string(),
            port: 1234,
        }) as Box<dyn EngineDriver + Send + Sync>;

        let engines = vec![vllm, ollama, lmstudio];
        let registry = build_model_registry(&engines).unwrap();

        assert_eq!(registry.models().len(), 4);
        assert!(registry.models().contains(&"llama-3".to_string()));
        assert!(registry.models().contains(&"mixtral".to_string()));
        assert!(registry.models().contains(&"phi-3".to_string()));
        assert!(registry.models().contains(&"gemma".to_string()));

        // "llama-3" is present in all three, should resolve to vllm URL
        assert_eq!(
            registry.get_engine_url("llama-3"),
            Some(&"http://localhost:8000".to_string())
        );

        // "phi-3" only in ollama
        assert_eq!(
            registry.get_engine_url("phi-3"),
            Some(&"http://localhost:11434".to_string())
        );

        // "gemma" only in lmstudio
        assert_eq!(
            registry.get_engine_url("gemma"),
            Some(&"http://localhost:1234".to_string())
        );

        // "mixtral" only in vllm
        assert_eq!(
            registry.get_engine_url("mixtral"),
            Some(&"http://localhost:8000".to_string())
        );
    }

    #[test]
    fn test_build_model_registry_no_models() {
        let vllm = Box::new(MockEngine {
            engine_type: "vllm".to_string(),
            models: vec![],
            base_url: "http://localhost:8000".to_string(),
            version: "0.4.1".to_string(),
            port: 8000,
        }) as Box<dyn EngineDriver + Send + Sync>;

        let engines = vec![vllm];
        let result = build_model_registry(&engines);

        assert!(result.is_err());
        assert_eq!(
            result.unwrap_err().to_string(),
            "No models found in any engine"
        );
    }

    #[test]
    fn test_build_model_registry_unexpected_engine() {
        let custom_engine = Box::new(MockEngine {
            engine_type: "custom".to_string(),
            models: vec!["custom-model".to_string()],
            base_url: "http://localhost:9999".to_string(),
            version: "1.0".to_string(),
            port: 9999,
        }) as Box<dyn EngineDriver + Send + Sync>;

        let engines = vec![custom_engine];
        let result = build_model_registry(&engines);

        // Custom engine types are not in priority list, so models won't be collected
        assert!(result.is_err());
        assert_eq!(
            result.unwrap_err().to_string(),
            "No models found in any engine"
        );
    }
}
