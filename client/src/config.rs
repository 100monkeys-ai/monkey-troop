use anyhow::Result;
use serde::Deserialize;
use std::env;

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    pub coordinator_url: String,
    pub proxy_port: u16,
    pub requester_id: String,
}

impl Config {
    pub fn from_env() -> Result<Self> {
        Ok(Config {
            coordinator_url: env::var("COORDINATOR_URL")
                .unwrap_or_else(|_| "https://troop.100monkeys.ai".to_string()),
            proxy_port: env::var("PROXY_PORT")
                .and_then(|s| s.parse().map_err(|_| env::VarError::NotPresent))
                .unwrap_or(9000),
            requester_id: env::var("REQUESTER_ID")
                .unwrap_or_else(|_| get_tailscale_ip().unwrap_or_else(|_| "unknown".to_string())),
        })
    }
}

fn get_tailscale_ip() -> Result<String> {
    use std::process::Command;

    let output = Command::new("tailscale").args(&["ip", "-4"]).output()?;

    if output.status.success() {
        let ip = String::from_utf8_lossy(&output.stdout);
        Ok(ip.trim().to_string())
    } else {
        Err(anyhow::anyhow!("Failed to get Tailscale IP"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;

    #[test]
    fn test_config_from_env() {
        // Since environment variables are global, we run all scenarios in one test
        // to avoid race conditions with other tests that might be added later.

        // Save original values to restore them later
        let orig_url = env::var("COORDINATOR_URL").ok();
        let orig_port = env::var("PROXY_PORT").ok();
        let orig_id = env::var("REQUESTER_ID").ok();

        // Scenario 1: Custom values
        env::set_var("COORDINATOR_URL", "http://localhost:8000");
        env::set_var("PROXY_PORT", "1234");
        env::set_var("REQUESTER_ID", "test-requester");

        let config = Config::from_env().unwrap();
        assert_eq!(config.coordinator_url, "http://localhost:8000");
        assert_eq!(config.proxy_port, 1234);
        assert_eq!(config.requester_id, "test-requester");

        // Scenario 2: Defaults
        env::remove_var("COORDINATOR_URL");
        env::remove_var("PROXY_PORT");
        env::remove_var("REQUESTER_ID");

        let config = Config::from_env().unwrap();
        assert_eq!(config.coordinator_url, "https://troop.100monkeys.ai");
        assert_eq!(config.proxy_port, 9000);
        assert!(!config.requester_id.is_empty());

        // Scenario 3: Invalid port
        env::set_var("PROXY_PORT", "not-a-number");
        let config = Config::from_env().unwrap();
        assert_eq!(config.proxy_port, 9000);

        // Restore original values
        if let Some(val) = orig_url {
            env::set_var("COORDINATOR_URL", val);
        } else {
            env::remove_var("COORDINATOR_URL");
        }
        if let Some(val) = orig_port {
            env::set_var("PROXY_PORT", val);
        } else {
            env::remove_var("PROXY_PORT");
        }
        if let Some(val) = orig_id {
            env::set_var("REQUESTER_ID", val);
        } else {
            env::remove_var("REQUESTER_ID");
        }
    }
}
