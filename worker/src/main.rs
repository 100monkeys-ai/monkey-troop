mod config;
mod engines;
mod gpu;
mod heartbeat;
mod proxy;
mod benchmark;

use anyhow::Result;
use tracing::{info, error};
use tracing_subscriber;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt::init();
    
    info!("🐒 Monkey Troop Worker starting...");
    
    // Load configuration
    let config = config::Config::from_env()?;
    info!("Configuration loaded: {}", config.node_id);
    
    // Optional: Run initial benchmark on startup
    if std::env::var("RUN_INITIAL_BENCHMARK").unwrap_or_default() == "true" {
        info!("Running initial hardware benchmark...");
        match benchmark::run_benchmark("startup", 4096).await {
            Ok(result) => {
                info!("✓ Benchmark: {}s on {}", result.duration, result.device_name);
            }
            Err(e) => {
                info!("Benchmark skipped: {}", e);
            }
        }
    }
    
    // Start heartbeat broadcaster
    let heartbeat_handle = tokio::spawn(heartbeat::run_heartbeat_loop(config.clone()));
    
    // Start JWT verification proxy
    let proxy_handle = tokio::spawn(proxy::run_proxy_server(config.clone()));
    
    // Wait for both tasks
    tokio::select! {
        res = heartbeat_handle => {
            error!("Heartbeat task ended: {:?}", res);
        }
        res = proxy_handle => {
            error!("Proxy task ended: {:?}", res);
        }
    }
    
    Ok(())
}
