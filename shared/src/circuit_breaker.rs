use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;

/// Circuit breaker state
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum CircuitState {
    Closed,   // Normal operation
    Open,     // Failures exceeded threshold, blocking requests
    HalfOpen, // Testing if service recovered
}

/// Simple circuit breaker implementation
pub struct CircuitBreaker {
    failure_count: AtomicU32,
    threshold: u32,
    timeout: Duration,
    state: Arc<RwLock<CircuitState>>,
    last_failure_time: Arc<RwLock<Option<Instant>>>,
}

impl CircuitBreaker {
    pub fn new(threshold: u32, timeout: Duration) -> Self {
        Self {
            failure_count: AtomicU32::new(0),
            threshold,
            timeout,
            state: Arc::new(RwLock::new(CircuitState::Closed)),
            last_failure_time: Arc::new(RwLock::new(None)),
        }
    }
    
    /// Check if request should be allowed
    pub async fn allow_request(&self) -> bool {
        let state = *self.state.read().await;
        
        match state {
            CircuitState::Closed => true,
            CircuitState::Open => {
                // Check if timeout has elapsed
                let last_failure = self.last_failure_time.read().await;
                if let Some(time) = *last_failure {
                    if time.elapsed() >= self.timeout {
                        // Try half-open
                        *self.state.write().await = CircuitState::HalfOpen;
                        true
                    } else {
                        false
                    }
                } else {
                    false
                }
            }
            CircuitState::HalfOpen => true,
        }
    }
    
    /// Record successful request
    pub async fn record_success(&self) {
        self.failure_count.store(0, Ordering::Relaxed);
        *self.state.write().await = CircuitState::Closed;
    }
    
    /// Record failed request
    pub async fn record_failure(&self) {
        let count = self.failure_count.fetch_add(1, Ordering::Relaxed) + 1;
        *self.last_failure_time.write().await = Some(Instant::now());
        
        if count >= self.threshold {
            *self.state.write().await = CircuitState::Open;
        }
    }
    
    /// Get current state
    pub async fn state(&self) -> CircuitState {
        *self.state.read().await
    }
}
