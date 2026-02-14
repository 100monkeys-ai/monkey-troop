use crate::{TroopError, TroopResult, MAX_RETRIES, RETRY_DELAYS};
use std::time::Duration;
use tokio::time::sleep;

// Use println! instead of tracing since we don't have tracing in shared crate
// Each application will log through their own tracing setup

/// Retry a fallible async operation with exponential backoff
pub async fn retry_with_backoff<F, Fut, T>(operation_name: &str, mut operation: F) -> TroopResult<T>
where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = TroopResult<T>>,
{
    let mut last_error = None;

    for attempt in 0..MAX_RETRIES {
        match operation().await {
            Ok(result) => {
                if attempt > 0 {
                    eprintln!(
                        "{} succeeded on retry attempt {}",
                        operation_name,
                        attempt + 1
                    );
                }
                return Ok(result);
            }
            Err(e) => {
                if attempt < MAX_RETRIES - 1 {
                    let delay = Duration::from_secs(RETRY_DELAYS[attempt as usize]);
                    eprintln!(
                        "{} failed (attempt {}): {}. Retrying in {:?}...",
                        operation_name,
                        attempt + 1,
                        e,
                        delay
                    );
                    sleep(delay).await;
                }
                last_error = Some(e);
            }
        }
    }

    Err(last_error.unwrap_or(TroopError::InternalError("Unknown retry error".to_string())))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU32, Ordering};
    use std::sync::Arc;

    #[tokio::test]
    async fn test_retry_succeeds_immediately() {
        let result = retry_with_backoff("test_op", || async { Ok::<_, TroopError>(42) }).await;

        assert!(result.is_ok());
        assert_eq!(result.unwrap(), 42);
    }

    #[tokio::test]
    async fn test_retry_succeeds_after_failures() {
        let counter = Arc::new(AtomicU32::new(0));
        let counter_clone = counter.clone();

        let result = retry_with_backoff("test_op", move || {
            let c = counter_clone.clone();
            async move {
                let count = c.fetch_add(1, Ordering::SeqCst);
                if count < 2 {
                    Err(TroopError::NetworkError("Temporary failure".to_string()))
                } else {
                    Ok(42)
                }
            }
        })
        .await;

        assert!(result.is_ok());
        assert_eq!(result.unwrap(), 42);
        assert_eq!(counter.load(Ordering::SeqCst), 3);
    }

    #[tokio::test]
    async fn test_retry_exhausts_attempts() {
        let counter = Arc::new(AtomicU32::new(0));
        let counter_clone = counter.clone();

        let result = retry_with_backoff("test_op", move || {
            let c = counter_clone.clone();
            async move {
                c.fetch_add(1, Ordering::SeqCst);
                Err::<i32, _>(TroopError::NetworkError("Permanent failure".to_string()))
            }
        })
        .await;

        assert!(result.is_err());
        assert_eq!(counter.load(Ordering::SeqCst), MAX_RETRIES);
    }
}
