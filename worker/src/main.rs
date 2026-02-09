mod config;
mod engines;
mod gpu;
mod heartbeat;
mod proxy;

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
