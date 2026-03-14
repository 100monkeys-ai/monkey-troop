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

#[cfg(test)]
mod tests {
    use super::*;
    use serial_test::serial;
    use std::env;

    #[test]
    #[serial]
    fn test_config_from_env() {
        // Save original values
        let orig_node_id = env::var("NODE_ID").ok();
        let orig_url = env::var("COORDINATOR_URL").ok();
        let orig_port = env::var("PROXY_PORT").ok();
        let orig_hb = env::var("HEARTBEAT_INTERVAL").ok();
        let orig_refresh = env::var("MODEL_REFRESH_INTERVAL").ok();

        // Scenario 1: Defaults
        env::remove_var("NODE_ID");
        env::remove_var("COORDINATOR_URL");
        env::remove_var("PROXY_PORT");
        env::remove_var("HEARTBEAT_INTERVAL");
        env::remove_var("MODEL_REFRESH_INTERVAL");

        let config = Config::from_env().unwrap();
        assert_eq!(config.coordinator_url, "https://troop.100monkeys.ai");
        assert_eq!(config.proxy_port, 8080);
        assert_eq!(config.heartbeat_interval, 10);
        assert_eq!(config.model_refresh_interval, 180);
        assert!(!config.node_id.is_empty());

        // Scenario 2: Custom
        env::set_var("NODE_ID", "test-node");
        env::set_var("COORDINATOR_URL", "http://localhost:8000");
        env::set_var("PROXY_PORT", "9999");
        env::set_var("HEARTBEAT_INTERVAL", "30");
        env::set_var("MODEL_REFRESH_INTERVAL", "600");

        let config = Config::from_env().unwrap();
        assert_eq!(config.node_id, "test-node");
        assert_eq!(config.coordinator_url, "http://localhost:8000");
        assert_eq!(config.proxy_port, 9999);
        assert_eq!(config.heartbeat_interval, 30);
        assert_eq!(config.model_refresh_interval, 600);

        // Restore
        if let Some(v) = orig_node_id { env::set_var("NODE_ID", v); } else { env::remove_var("NODE_ID"); }
        if let Some(v) = orig_url { env::set_var("COORDINATOR_URL", v); } else { env::remove_var("COORDINATOR_URL"); }
        if let Some(v) = orig_port { env::set_var("PROXY_PORT", v); } else { env::remove_var("PROXY_PORT"); }
        if let Some(v) = orig_hb { env::set_var("HEARTBEAT_INTERVAL", v); } else { env::remove_var("HEARTBEAT_INTERVAL"); }
        if let Some(v) = orig_refresh { env::set_var("MODEL_REFRESH_INTERVAL", v); } else { env::remove_var("MODEL_REFRESH_INTERVAL"); }
    }
}
