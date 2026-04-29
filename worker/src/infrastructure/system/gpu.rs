use crate::application::ports::HardwareMonitor;
use crate::domain::models::HardwareStatus;
use anyhow::Result;
use async_trait::async_trait;
use std::process::Command;
use sysinfo::System;

pub struct NvidiaGpuMonitor;

#[async_trait]
impl HardwareMonitor for NvidiaGpuMonitor {
    async fn get_status(&self) -> Result<HardwareStatus> {
        let (name, vram) = get_gpu_info();
        Ok(HardwareStatus {
            gpu_name: name,
            vram_free_mb: vram,
        })
    }

    async fn is_idle(&self) -> Result<bool> {
        // Use a 10% utilization threshold for "IDLE" status
        self.is_gpu_idle(10.0).await
    }
}

impl NvidiaGpuMonitor {
    /// Check if GPU is idle based on utilization threshold
    pub async fn is_gpu_idle(&self, threshold: f32) -> Result<bool> {
        // Try nvidia-smi first on a blocking thread to avoid blocking the async runtime
        if let Ok(Ok(nvidia_idle)) =
            tokio::task::spawn_blocking(move || check_nvidia_idle(threshold)).await
        {
            return Ok(nvidia_idle);
        }

        // Fallback: check CPU idle as proxy
        Ok(check_cpu_idle(threshold).await)
    }
}

/// Free functions for GPU and CPU checks to avoid lifetime issues with spawn_blocking
fn check_nvidia_idle(threshold: f32) -> Result<bool> {
    let output = Command::new(monkey_troop_shared::get_secure_binary_path("nvidia-smi")?)
        .args([
            "--query-gpu=utilization.gpu",
            "--format=csv,noheader,nounits",
        ])
        .output()?;

    if output.status.success() {
        let stdout = String::from_utf8_lossy(&output.stdout);
        if let Some(line) = stdout.lines().next() {
            if let Ok(util) = line.trim().parse::<f32>() {
                return Ok(util < threshold);
            }
        }
    }

    Err(anyhow::anyhow!("Failed to parse nvidia-smi output"))
}

async fn check_cpu_idle(threshold: f32) -> bool {
    let mut sys = System::new_all();
    sys.refresh_cpu_all();

    // Wait a bit for accurate CPU measurement
    tokio::time::sleep(std::time::Duration::from_millis(200)).await;
    sys.refresh_cpu_all();

    let avg_usage =
        sys.cpus().iter().map(|cpu| cpu.cpu_usage()).sum::<f32>() / sys.cpus().len() as f32;

    avg_usage < threshold
}

fn get_gpu_info() -> (String, u64) {
    if let Ok((name, vram)) = get_nvidia_info() {
        return (name, vram);
    }

    // Fallback
    ("Unknown GPU".to_string(), 0)
}

fn get_nvidia_info() -> Result<(String, u64)> {
    // Get GPU name
    let name_output = Command::new(monkey_troop_shared::get_secure_binary_path("nvidia-smi")?)
        .args(["--query-gpu=name", "--format=csv,noheader"])
        .output()?;

    let name = String::from_utf8_lossy(&name_output.stdout)
        .trim()
        .to_string();

    // Get free VRAM in MB
    let vram_output = Command::new(monkey_troop_shared::get_secure_binary_path("nvidia-smi")?)
        .args(["--query-gpu=memory.free", "--format=csv,noheader,nounits"])
        .output()?;

    let vram = String::from_utf8_lossy(&vram_output.stdout)
        .trim()
        .parse::<u64>()
        .unwrap_or(0);

    Ok((name, vram))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_get_status() {
        let monitor = NvidiaGpuMonitor;
        let status = monitor.get_status().await.unwrap();
        // Even without nvidia-smi, it should return "Unknown GPU"
        assert!(!status.gpu_name.is_empty());
    }

    #[tokio::test]
    async fn test_is_idle() {
        let monitor = NvidiaGpuMonitor;
        let idle = monitor.is_idle().await;
        // Should fallback to CPU check if nvidia-smi fails
        assert!(idle.is_ok());
    }
}
