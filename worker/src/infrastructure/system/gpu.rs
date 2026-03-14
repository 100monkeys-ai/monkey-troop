use crate::application::ports::HardwareMonitor;
use crate::domain::models::HardwareStatus;
use anyhow::Result;
use async_trait::async_trait;

pub struct NvidiaGpuMonitor;

#[async_trait]
impl HardwareMonitor for NvidiaGpuMonitor {
    async fn get_status(&self) -> Result<HardwareStatus> {
        // Placeholder for real detection (wrapping current gpu.rs logic later)
        Ok(HardwareStatus {
            gpu_name: "NVIDIA GeForce RTX 4090".to_string(),
            vram_free_mb: 24576,
        })
    }
}
