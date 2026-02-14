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
    if ollama.detect().is_ok() {
        println!("✓ Detected Ollama");
        engines.push(Box::new(ollama));
    }

    // Try vLLM
    let vllm = vllm::VllmDriver::new();
    if vllm.detect().is_ok() {
        println!("✓ Detected vLLM");
        engines.push(Box::new(vllm));
    }

    // Try LM Studio
    let lmstudio = lmstudio::LMStudioDriver::new();
    if lmstudio.detect().is_ok() {
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
