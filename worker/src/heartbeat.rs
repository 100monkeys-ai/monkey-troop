use crate::config::Config;
use crate::engines::{self, ModelRegistry};
use crate::gpu;
use monkey_troop_shared::{NodeHeartbeat, NodeStatus, HardwareInfo, CircuitBreaker, CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_TIMEOUT};
use anyhow::Result;
use std::time::{Duration, Instant};
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::sleep;
use tracing::{info, warn};

pub async fn run_heartbeat_loop(config: Config, registry: Arc<RwLock<ModelRegistry>>) -> Result<()> {
    let client = reqwest::Client::new();
    let heartbeat_url = format!("{}/heartbeat", config.coordinator_url);
    
    // Circuit breaker to avoid spamming coordinator when offline
    let circuit_breaker = Arc::new(CircuitBreaker::new(
        CIRCUIT_BREAKER_THRESHOLD,
        CIRCUIT_BREAKER_TIMEOUT
    ));
    
    // Get Tailscale IP
    let tailscale_ip = get_tailscale_ip().unwrap_or_else(|_| "unknown".to_string());
    
    info!("Starting heartbeat loop (every {}s)", config.heartbeat_interval);
    info!("Model refresh interval: {}s", config.model_refresh_interval);
    info!("Tailscale IP: {}", tailscale_ip);
    
    let mut last_model_refresh = Instant::now();
    let mut last_models: Vec<String> = Vec::new();
    let mut last_engines: Vec<monkey_troop_shared::EngineInfo> = Vec::new();
    
    loop {
        // Check if we need to refresh model registry
        let should_refresh = last_model_refresh.elapsed().as_secs() >= config.model_refresh_interval;
        
        if should_refresh {
            info!("🔄 Refreshing model registry...");
            match refresh_model_registry(&registry).await {
                Ok(_) => {
                    last_model_refresh = Instant::now();
                    info!("✓ Model registry refreshed");
                }
                Err(e) => {
                    warn!("Failed to refresh model registry: {}", e);
                }
            }
        }
        
        // Check circuit breaker
        if !circuit_breaker.allow_request().await {
            warn!("Circuit breaker OPEN - skipping heartbeat attempt");
            sleep(Duration::from_secs(config.heartbeat_interval)).await;
            continue;
        }
        
        match send_heartbeat(&client, &heartbeat_url, &config, &tailscale_ip, &registry, &mut last_models, &mut last_engines).await {
            Ok(sent) => {
                if sent {
                    info!("✓ Heartbeat sent successfully");
                }
                circuit_breaker.record_success().await;
            }
            Err(e) => {
                warn!("Failed to send heartbeat: {}", e);
                circuit_breaker.record_failure().await;
            }
        }
        
        sleep(Duration::from_secs(config.heartbeat_interval)).await;
    }
}

async fn send_heartbeat(
    client: &reqwest::Client,
    url: &str,
    config: &Config,
    tailscale_ip: &str,
    registry: &Arc<RwLock<ModelRegistry>>,
    last_models: &mut Vec<String>,
    last_engines: &mut Vec<monkey_troop_shared::EngineInfo>,
) -> Result<bool> {
    // Get current registry state
    let registry_read = registry.read().await;
    let models = registry_read.models().to_vec();
    let engines = registry_read.engines().to_vec();
    drop(registry_read);
    
    // Check if there are actual changes
    let models_changed = models != *last_models;
    let engines_changed = engines.len() != last_engines.len() 
        || engines.iter().zip(last_engines.iter()).any(|(a, b)| {
            a.engine_type != b.engine_type || a.version != b.version || a.port != b.port
        });
    
    // Only send heartbeat if something changed
    if !models_changed && !engines_changed {
        return Ok(false); // No changes, no need to send
    }
    
    info!("📡 Changes detected - sending heartbeat update");
    if models_changed {
        info!("  Models: {} -> {}", last_models.len(), models.len());
    }
    if engines_changed {
        info!("  Engines: {} -> {}", last_engines.len(), engines.len());
    }
    
    // Get GPU info
    let (gpu_name, vram_free) = gpu::get_gpu_info();
    
    // Determine status
    let status = if gpu::is_gpu_idle(10.0).unwrap_or(false) {
        NodeStatus::Idle
    } else {
        NodeStatus::Busy
    };
    
    let heartbeat = NodeHeartbeat {
        node_id: config.node_id.clone(),
        tailscale_ip: tailscale_ip.to_string(),
        status,
        models: models.clone(),
        hardware: HardwareInfo {
            gpu: gpu_name,
            vram_free,
        },
        engines: engines.clone(),
    };
    
    client
        .post(url)
        .json(&heartbeat)
        .timeout(Duration::from_secs(5))
        .send()
        .await?;
    
    // Update cache
    *last_models = models;
    *last_engines = engines;
    
    Ok(true) // Heartbeat was sent
}

async fn refresh_model_registry(registry: &Arc<RwLock<ModelRegistry>>) -> Result<()> {
    // Detect all engines
    let engines = engines::detect_all_engines().await;
    
    if engines.is_empty() {
        return Err(anyhow::anyhow!("No engines detected"));
    }
    
    // Build new registry
    let new_registry = engines::build_model_registry(&engines)?;
    
    // Update shared registry
    let mut registry_write = registry.write().await;
    *registry_write = new_registry;
    
    Ok(())
}

fn get_tailscale_ip() -> Result<String> {
    use std::process::Command;
    
    let output = Command::new("tailscale")
        .args(&["ip", "-4"])
        .output()?;
    
    if output.status.success() {
        let ip = String::from_utf8_lossy(&output.stdout);
        Ok(ip.trim().to_string())
    } else {
        Err(anyhow::anyhow!("Failed to get Tailscale IP"))
    }
}
