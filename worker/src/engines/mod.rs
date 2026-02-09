pub mod ollama;
pub mod lmstudio;

use anyhow::Result;
use monkey_troop_shared::EngineInfo;

/// Trait for inference engine drivers
pub trait EngineDriver {
    fn detect(&self) -> Result<bool>;
    fn get_info(&self) -> Result<EngineInfo>;
    fn get_models(&self) -> Result<Vec<String>>;
}

/// Detect available engines and return the first one found
pub async fn detect_engine() -> Result<Box<dyn EngineDriver + Send + Sync>> {
    // Try Ollama first
    let ollama = ollama::OllamaDriver::new();
    if ollama.detect().is_ok() {
        return Ok(Box::new(ollama));
    }
    
    // Try LM Studio
    let lmstudio = lmstudio::LMStudioDriver::new();
    if lmstudio.detect().is_ok() {
        return Ok(Box::new(lmstudio));
    }
    
    Err(anyhow::anyhow!("No inference engine detected"))
}
