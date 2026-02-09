use crate::config::Config;
use crate::engines;
use crate::gpu;
use monkey_troop_shared::{NodeHeartbeat, NodeStatus, HardwareInfo, CircuitBreaker, CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_TIMEOUT};
use anyhow::Result;
use std::time::Duration;
use std::sync::Arc;
use tokio::time::sleep;
use tracing::{info, warn};

pub async fn run_heartbeat_loop(config: Config) -> Result<()> {
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
    info!("Tailscale IP: {}", tailscale_ip);
    
    loop {
        // Check circuit breaker
        if !circuit_breaker.allow_request().await {
            warn!("Circuit breaker OPEN - skipping heartbeat attempt");
            sleep(Duration::from_secs(config.heartbeat_interval)).await;
            continue;
        }
        
        match send_heartbeat(&client, &heartbeat_url, &config, &tailscale_ip).await {
            Ok(_) => {
                info!("✓ Heartbeat sent successfully");
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
) -> Result<()> {
    // Detect engine
    let engine = match engines::detect_engine().await {
        Ok(e) => e,
        Err(e) => {
            warn!("No engine detected: {}", e);
            return Err(e);
        }
    };
    
    let engine_info = engine.get_info()?;
    let models = engine.get_models()?;
    
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
        models,
        hardware: HardwareInfo {
            gpu: gpu_name,
            vram_free,
        },
        engine: engine_info,
    };
    
    client
        .post(url)
        .json(&heartbeat)
        .timeout(Duration::from_secs(5))
        .send()
        .await?;
    
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
