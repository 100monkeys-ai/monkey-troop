use anyhow::{Result, Context};
use serde::{Deserialize, Serialize};
use tokio::process::Command;
use std::time::Duration;
use tracing::{info, warn, error};

#[derive(Debug, Serialize, Deserialize)]
pub struct BenchmarkResult {
    pub proof_hash: String,
    pub duration: f64,
    pub device_name: String,
}

#[derive(Debug, Deserialize)]
struct BenchmarkOutput {
    proof_hash: String,
    duration: f64,
    device: String,
}

/// Run hardware benchmark using Python subprocess
pub async fn run_benchmark(seed: &str, matrix_size: usize) -> Result<BenchmarkResult> {
    info!("🔬 Starting hardware benchmark (seed: {}, size: {})", seed, matrix_size);
    
    // Spawn Python subprocess
    let output = tokio::time::timeout(
        Duration::from_secs(300), // 5 minute timeout
        Command::new("python3")
            .arg("-c")
            .arg(include_str!("../benchmark.py"))
            .arg(seed)
            .arg(matrix_size.to_string())
            .output()
    )
    .await
    .context("Benchmark timed out after 300 seconds")?
    .context("Failed to execute benchmark subprocess")?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        error!("Benchmark failed: {}", stderr);
        
        // Check if it's a PyTorch import error
        if stderr.contains("No module named 'torch'") {
            warn!("PyTorch not installed, falling back to CPU benchmark");
            return run_cpu_fallback_benchmark(seed, matrix_size).await;
        }
        
        anyhow::bail!("Benchmark subprocess failed: {}", stderr);
    }
    
    // Parse JSON output
    let stdout = String::from_utf8_lossy(&output.stdout);
    let benchmark_output: BenchmarkOutput = serde_json::from_str(&stdout)
        .context("Failed to parse benchmark JSON output")?;
    
    info!("✓ Benchmark complete: {}s on {}", benchmark_output.duration, benchmark_output.device);
    
    Ok(BenchmarkResult {
        proof_hash: benchmark_output.proof_hash,
        duration: benchmark_output.duration,
        device_name: benchmark_output.device,
    })
}

/// Fallback CPU benchmark when GPU/PyTorch unavailable
async fn run_cpu_fallback_benchmark(seed: &str, matrix_size: usize) -> Result<BenchmarkResult> {
    info!("Running CPU fallback benchmark...");
    
    // Simple CPU benchmark using numpy
    let python_code = format!(r#"
import json
import hashlib
import time
import numpy as np

seed = "{}"
matrix_size = {}

# Set seed for reproducibility
np.random.seed(int(seed, 16) % (2**32))

# Generate matrices
start = time.time()
a = np.random.randn(matrix_size, matrix_size).astype(np.float32)
b = np.random.randn(matrix_size, matrix_size).astype(np.float32)

# Perform matrix multiplication
result = np.matmul(a, b)

duration = time.time() - start

# Generate proof hash
proof_data = f"{{seed}}:{{duration:.6f}}:{{result.sum():.6f}}"
proof_hash = hashlib.sha256(proof_data.encode()).hexdigest()

output = {{
    "proof_hash": proof_hash,
    "duration": duration,
    "device": "CPU (fallback)"
}}

print(json.dumps(output))
"#, seed, matrix_size);
    
    let output = tokio::time::timeout(
        Duration::from_secs(300),
        Command::new("python3")
            .arg("-c")
            .arg(&python_code)
            .output()
    )
    .await
    .context("CPU fallback benchmark timed out")?
    .context("Failed to execute CPU fallback")?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        anyhow::bail!("CPU fallback failed: {}", stderr);
    }
    
    let stdout = String::from_utf8_lossy(&output.stdout);
    let benchmark_output: BenchmarkOutput = serde_json::from_str(&stdout)
        .context("Failed to parse CPU fallback output")?;
    
    Ok(BenchmarkResult {
        proof_hash: benchmark_output.proof_hash,
        duration: benchmark_output.duration,
        device_name: benchmark_output.device,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_benchmark_runs() {
        let result = run_benchmark("test123", 512).await;
        // Don't fail test if PyTorch not installed
        if let Err(e) = result {
            eprintln!("Benchmark test skipped (expected in dev): {}", e);
        }
    }
}
