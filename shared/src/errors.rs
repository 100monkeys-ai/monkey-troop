use std::fmt;
use std::time::Duration;

/// Timeout constants for network operations
pub const DISCOVERY_TIMEOUT: Duration = Duration::from_secs(5);
pub const AUTH_TIMEOUT: Duration = Duration::from_secs(30);
pub const INFERENCE_TIMEOUT: Duration = Duration::from_secs(300);

/// Retry configuration
pub const MAX_RETRIES: u32 = 3;
pub const RETRY_DELAYS: [u64; 3] = [1, 2, 4]; // seconds

/// Circuit breaker configuration
pub const CIRCUIT_BREAKER_THRESHOLD: u32 = 5;
pub const CIRCUIT_BREAKER_TIMEOUT: Duration = Duration::from_secs(60);

/// Standard error types for Monkey Troop
#[derive(Debug)]
pub enum TroopError {
    /// Network connection failed
    NetworkError(String),

    /// Request timed out
    Timeout(String),

    /// Authentication/authorization failed
    AuthError(String),

    /// No nodes available to service request
    NoNodesAvailable,

    /// Insufficient credits
    InsufficientCredits { required: u64, available: u64 },

    /// Invalid request format
    InvalidRequest(String),

    /// Worker is busy or unavailable
    WorkerUnavailable(String),

    /// Circuit breaker is open
    CircuitBreakerOpen,

    /// Internal server error
    InternalError(String),
}

impl fmt::Display for TroopError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            TroopError::NetworkError(msg) => write!(f, "Network error: {}", msg),
            TroopError::Timeout(msg) => write!(f, "Timeout: {}", msg),
            TroopError::AuthError(msg) => write!(f, "Authentication error: {}", msg),
            TroopError::NoNodesAvailable => write!(f, "No nodes available to service request"),
            TroopError::InsufficientCredits {
                required,
                available,
            } => {
                write!(
                    f,
                    "Insufficient credits: need {}, have {}",
                    required, available
                )
            }
            TroopError::InvalidRequest(msg) => write!(f, "Invalid request: {}", msg),
            TroopError::WorkerUnavailable(msg) => write!(f, "Worker unavailable: {}", msg),
            TroopError::CircuitBreakerOpen => {
                write!(f, "Circuit breaker open, service temporarily unavailable")
            }
            TroopError::InternalError(msg) => write!(f, "Internal error: {}", msg),
        }
    }
}

impl std::error::Error for TroopError {}

// Convert from common error types
impl From<reqwest::Error> for TroopError {
    fn from(err: reqwest::Error) -> Self {
        if err.is_timeout() {
            TroopError::Timeout(err.to_string())
        } else if err.is_connect() {
            TroopError::NetworkError(err.to_string())
        } else {
            TroopError::InternalError(err.to_string())
        }
    }
}

impl From<serde_json::Error> for TroopError {
    fn from(err: serde_json::Error) -> Self {
        TroopError::InvalidRequest(err.to_string())
    }
}

impl From<std::io::Error> for TroopError {
    fn from(err: std::io::Error) -> Self {
        TroopError::InternalError(err.to_string())
    }
}

impl From<anyhow::Error> for TroopError {
    fn from(err: anyhow::Error) -> Self {
        TroopError::InternalError(err.to_string())
    }
}

/// Result type alias using TroopError
pub type TroopResult<T> = Result<T, TroopError>;
