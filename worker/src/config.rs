use anyhow::Result;
use std::env;

#[derive(Debug, Clone, serde::Deserialize)]
pub struct Config {
    pub node_id: String,
    pub coordinator_url: String,
    #[allow(dead_code)]
    pub proxy_port: u16,
    #[allow(dead_code)]
    pub heartbeat_interval: u64, // seconds
    #[allow(dead_code)]
    pub model_refresh_interval: u64, // seconds
}

impl Config {
    pub fn from_env() -> Result<Self> {
        Ok(Config {
            node_id: env::var("NODE_ID").unwrap_or_else(|_| {
                hostname::get()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .to_string()
            }),
            coordinator_url: env::var("COORDINATOR_URL")
                .unwrap_or_else(|_| "https://troop.100monkeys.ai".to_string()),
            proxy_port: env::var("PROXY_PORT")
                .and_then(|s| s.parse().map_err(|_| env::VarError::NotPresent))
                .unwrap_or(8080),
            heartbeat_interval: env::var("HEARTBEAT_INTERVAL")
                .and_then(|s| s.parse().map_err(|_| env::VarError::NotPresent))
                .unwrap_or(10),
            model_refresh_interval: env::var("MODEL_REFRESH_INTERVAL")
                .and_then(|s| s.parse().map_err(|_| env::VarError::NotPresent))
                .unwrap_or(180), // 3 minutes default
        })
    }
}
