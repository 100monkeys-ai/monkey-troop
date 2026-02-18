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
