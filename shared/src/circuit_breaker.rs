use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tokio::time::Instant;

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

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[tokio::test]
    async fn test_circuit_breaker_initial_state() {
        let cb = CircuitBreaker::new(3, Duration::from_millis(100));
        assert_eq!(cb.state().await, CircuitState::Closed);
        assert!(cb.allow_request().await);
    }

    #[tokio::test]
    async fn test_circuit_breaker_threshold() {
        let cb = CircuitBreaker::new(3, Duration::from_millis(100));

        cb.record_failure().await;
        cb.record_failure().await;
        assert_eq!(cb.state().await, CircuitState::Closed);
        assert!(cb.allow_request().await);

        cb.record_failure().await;
        assert_eq!(cb.state().await, CircuitState::Open);
        assert!(!cb.allow_request().await);
    }

    #[tokio::test]
    async fn test_circuit_breaker_timeout() {
        tokio::time::pause();
        let cb = CircuitBreaker::new(1, Duration::from_millis(50));

        cb.record_failure().await;
        assert_eq!(cb.state().await, CircuitState::Open);
        assert!(!cb.allow_request().await);

        tokio::time::advance(Duration::from_millis(60)).await;

        assert!(cb.allow_request().await);
        assert_eq!(cb.state().await, CircuitState::HalfOpen);
    }

    #[tokio::test]
    async fn test_circuit_breaker_reset() {
        tokio::time::pause();
        let cb = CircuitBreaker::new(1, Duration::from_millis(50));

        cb.record_failure().await;
        assert_eq!(cb.state().await, CircuitState::Open);

        tokio::time::advance(Duration::from_millis(60)).await;
        cb.allow_request().await; // Move to HalfOpen
        assert_eq!(cb.state().await, CircuitState::HalfOpen);

        cb.record_success().await;
        assert_eq!(cb.state().await, CircuitState::Closed);

        // Verify count reset: should need another failure to trip
        cb.record_failure().await;
        assert_eq!(cb.state().await, CircuitState::Open);
    }

    #[tokio::test]
    async fn test_circuit_breaker_half_open_failure() {
        tokio::time::pause();
        let cb = CircuitBreaker::new(1, Duration::from_millis(50));

        cb.record_failure().await;
        tokio::time::advance(Duration::from_millis(60)).await;
        cb.allow_request().await; // Move to HalfOpen
        assert_eq!(cb.state().await, CircuitState::HalfOpen);

        cb.record_failure().await;
        assert_eq!(cb.state().await, CircuitState::Open);
        assert!(!cb.allow_request().await);
    }
}
