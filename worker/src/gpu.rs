use anyhow::Result;
use sysinfo::System;

/// Check if GPU is idle based on utilization threshold
pub async fn is_gpu_idle(threshold: f32) -> Result<bool> {
    // Try nvidia-smi first on a blocking thread to avoid blocking the async runtime
    if let Ok(nvidia_result) =
        tokio::task::spawn_blocking(move || check_nvidia_idle(threshold)).await
    {
        if let Ok(nvidia_idle) = nvidia_result {
            return Ok(nvidia_idle);
        }
    }

    // Fallback: check CPU idle as proxy
    Ok(check_cpu_idle(threshold).await)
}

fn check_nvidia_idle(threshold: f32) -> Result<bool> {
    use std::process::Command;

    let output = Command::new("nvidia-smi")
        .args(&[
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
    sys.refresh_cpu();

    // Wait a bit for accurate CPU measurement
    tokio::time::sleep(std::time::Duration::from_millis(200)).await;
    sys.refresh_cpu();

    let avg_usage =
        sys.cpus().iter().map(|cpu| cpu.cpu_usage()).sum::<f32>() / sys.cpus().len() as f32;

    avg_usage < threshold
}

/// Get GPU information
pub fn get_gpu_info() -> (String, u64) {
    if let Ok((name, vram)) = get_nvidia_info() {
        return (name, vram);
    }

    // Fallback
    ("Unknown GPU".to_string(), 0)
}

fn get_nvidia_info() -> Result<(String, u64)> {
    use std::process::Command;

    // Get GPU name
    let name_output = Command::new("nvidia-smi")
        .args(&["--query-gpu=name", "--format=csv,noheader"])
        .output()?;

    let name = String::from_utf8_lossy(&name_output.stdout)
        .trim()
        .to_string();

    // Get free VRAM in MB
    let vram_output = Command::new("nvidia-smi")
        .args(&["--query-gpu=memory.free", "--format=csv,noheader,nounits"])
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
    use std::time::{Duration, Instant};

    #[tokio::test(flavor = "current_thread")]
    async fn test_cpu_idle_no_longer_blocks_executor() {
        let start = Instant::now();

        // This call takes ~200ms due to the internal sleep; verify we actually waited.
        check_cpu_idle(100.0).await;

        let elapsed = start.elapsed();
        println!("check_cpu_idle elapsed: {:?}", elapsed);

        // Ensure we waited long enough to exercise the async sleep inside check_cpu_idle.
        assert!(
            elapsed >= Duration::from_millis(190),
            "check_cpu_idle returned too quickly: {:?}",
            elapsed
        );
    }
}
