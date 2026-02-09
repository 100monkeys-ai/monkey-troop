mod config;
mod proxy;

use anyhow::Result;
use clap::{Parser, Subcommand};
use tracing::info;
use tracing_subscriber;

#[derive(Parser)]
#[command(name = "monkey-troop-client")]
#[command(about = "Monkey Troop Client - Access distributed AI compute", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Start the local proxy server
    Up,
    /// Check credit balance
    Balance,
    /// List available nodes
    Nodes,
}

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt::init();
    
    let cli = Cli::parse();
    
    match cli.command {
        Commands::Up => {
            info!("🐒 Monkey Troop Client starting...");
            let config = config::Config::from_env()?;
            proxy::run_proxy_server(config).await?;
        }
        Commands::Balance => {
            info!("Checking balance...");
            // TODO: Implement balance check
            println!("Balance check not yet implemented");
        }
        Commands::Nodes => {
            info!("Listing available nodes...");
            let config = config::Config::from_env()?;
            list_nodes(&config).await?;
        }
    }
    
    Ok(())
}

async fn list_nodes(config: &config::Config) -> Result<()> {
    let client = reqwest::Client::new();
    let url = format!("{}/peers", config.coordinator_url);
    
    let response: serde_json::Value = client
        .get(&url)
        .send()
        .await?
        .json()
        .await?;
    
    println!("{}", serde_json::to_string_pretty(&response)?);
    
    Ok(())
}
