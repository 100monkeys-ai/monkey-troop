mod domain;
mod application;
mod infrastructure;
mod presentation;
mod config;

use anyhow::Result;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{error, info};

use crate::domain::models::ModelRegistry;
use crate::application::services::WorkerService;
use crate::infrastructure::engines::ollama::OllamaEngine;
use crate::infrastructure::system::gpu::NvidiaGpuMonitor;
use crate::infrastructure::system::coordinator::HttpCoordinatorClient;
use crate::presentation::api::proxy::{create_proxy_router, ProxyState};

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt::init();
    info!("🐒 Monkey Troop Worker (DDD Aligned) starting...");

    let config = config::Config::from_env()?;
    
    // Core state
    let registry = Arc::new(RwLock::new(ModelRegistry::new()));
    
    // Dependencies (Infrastructure)
    let engines: Vec<Box<dyn crate::application::ports::InferenceEngine>> = vec![
        Box::new(OllamaEngine::new()),
    ];
    let monitor = Arc::new(NvidiaGpuMonitor);
    let coordinator = Arc::new(HttpCoordinatorClient::new(config.coordinator_url.clone()));

    // Application Service
    let service = Arc::new(WorkerService::new(
        config.node_id.clone(),
        registry.clone(),
        engines,
        monitor,
        coordinator,
    ));

    // 1. Initial registry refresh
    service.refresh_model_registry().await?;

    // 2. Start heartbeat loop
    let service_heartbeat = service.clone();
    let heartbeat_handle = tokio::spawn(async move {
        let mut interval = tokio::time::interval(std::time::Duration::from_secs(10));
        loop {
            interval.tick().await;
            if let Err(e) = service_heartbeat.send_heartbeat().await {
                error!("Heartbeat failed: {}", e);
            }
        }
    });

    // 3. Start Proxy API (Presentation Layer)
    let proxy_state = Arc::new(ProxyState {
        service: service.clone(),
    });
    let app = create_proxy_router(proxy_state);
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8001").await?;
    info!("✓ Proxy API listening on :8001");
    
    let proxy_handle = tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

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
