mod config;
mod proxy;

use anyhow::Result;
use clap::{Parser, Subcommand};
use tracing::info;

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
    /// List transaction history
    Transactions,
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
            let config = config::Config::from_env()?;
            check_balance(&config).await?;
        }
        Commands::Nodes => {
            info!("Listing available nodes...");
            let config = config::Config::from_env()?;
            list_nodes(&config).await?;
        }
        Commands::Transactions => {
            info!("Fetching transactions...");
            let config = config::Config::from_env()?;
            list_transactions(&config).await?;
        }
    }

    Ok(())
}

async fn check_balance(config: &config::Config) -> Result<()> {
    let client = reqwest::Client::new();
    let url = format!(
        "{}/users/{}/balance",
        config.coordinator_url, config.requester_id
    );

    let response = client.get(&url).send().await?;

    if response.status().is_success() {
        let balance: serde_json::Value = response.json().await?;
        println!("{}", serde_json::to_string_pretty(&balance)?);
    } else {
        println!("Failed to get balance: {}", response.status());
    }

    Ok(())
}

async fn list_transactions(config: &config::Config) -> Result<()> {
    let client = reqwest::Client::new();
    let url = format!(
        "{}/users/{}/transactions",
        config.coordinator_url, config.requester_id
    );

    let response = client.get(&url).send().await?;

    if response.status().is_success() {
        let transactions: serde_json::Value = response.json().await?;
        println!("{}", serde_json::to_string_pretty(&transactions)?);
    } else {
        println!("Failed to get transactions: {}", response.status());
    }

    Ok(())
}

async fn list_nodes(config: &config::Config) -> Result<()> {
    let client = reqwest::Client::new();
    let url = format!("{}/peers", config.coordinator_url);

    let response: serde_json::Value = client.get(&url).send().await?.json().await?;

    println!("{}", serde_json::to_string_pretty(&response)?);

    Ok(())
}
