use anyhow::{Context, Result};
use std::env;

#[derive(Debug, Clone, serde::Deserialize)]
pub struct Config {
    pub node_id: String,
    pub coordinator_url: String,
    // This field is deserialized from environment/config and kept for compatibility with
    // external components, even if it's not currently read within this crate.
    #[allow(dead_code)]
    pub proxy_port: u16,
    // This field controls worker heartbeat behavior; it's retained for future/optional use
    // and may be read by other parts of the system not analyzed here.
    #[allow(dead_code)]
    pub heartbeat_interval: u64, // seconds
    // This field configures how often models are refreshed; it's intentionally kept for
    // future/optional use, so we suppress dead_code warnings.
    #[allow(dead_code)]
    pub model_refresh_interval: u64, // seconds
}

impl Config {
    fn parse_env_with_default<T>(var_name: &str, default: T) -> Result<T>
    where
        T: std::str::FromStr,
        <T as std::str::FromStr>::Err: std::error::Error + Send + Sync + 'static,
    {
        match env::var(var_name) {
            Ok(s) => s
                .parse()
                .with_context(|| format!("Invalid value for {var_name}: {s}")),
            Err(env::VarError::NotPresent) => Ok(default),
            Err(e) => Err(e).context(format!("Failed to read {var_name} environment variable")),
        }
    }

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
            proxy_port: Self::parse_env_with_default("PROXY_PORT", 8080u16)?,
            heartbeat_interval: Self::parse_env_with_default("HEARTBEAT_INTERVAL", 10u64)?,
            model_refresh_interval: Self::parse_env_with_default(
                "MODEL_REFRESH_INTERVAL",
                180u64, // 3 minutes default
            )?,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serial_test::serial;
    use std::env;

    fn restore_env_var(name: &str, value: Option<String>) {
        if let Some(v) = value {
            env::set_var(name, v);
        } else {
            env::remove_var(name);
        }
    }

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
        restore_env_var("NODE_ID", orig_node_id);
        restore_env_var("COORDINATOR_URL", orig_url);
        restore_env_var("PROXY_PORT", orig_port);
        restore_env_var("HEARTBEAT_INTERVAL", orig_hb);
        restore_env_var("MODEL_REFRESH_INTERVAL", orig_refresh);
    }
}
