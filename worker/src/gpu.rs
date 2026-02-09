use anyhow::Result;
use sysinfo::System;

/// Check if GPU is idle based on utilization threshold
pub fn is_gpu_idle(threshold: f32) -> Result<bool> {
    // Try nvidia-smi first
    if let Ok(nvidia_idle) = check_nvidia_idle(threshold) {
        return Ok(nvidia_idle);
    }
    
    // Fallback: check CPU idle as proxy
    Ok(check_cpu_idle(threshold))
}

fn check_nvidia_idle(threshold: f32) -> Result<bool> {
    use std::process::Command;
    
    let output = Command::new("nvidia-smi")
        .args(&["--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"])
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

fn check_cpu_idle(threshold: f32) -> bool {
    let mut sys = System::new_all();
    sys.refresh_cpu();
    
    // Wait a bit for accurate CPU measurement
    std::thread::sleep(std::time::Duration::from_millis(200));
    sys.refresh_cpu();
    
    let avg_usage = sys.cpus().iter().map(|cpu| cpu.cpu_usage()).sum::<f32>() 
        / sys.cpus().len() as f32;
    
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
