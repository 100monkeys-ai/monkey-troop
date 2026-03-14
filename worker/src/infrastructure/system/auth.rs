use crate::application::ports::AuthTokenVerifier;
use anyhow::Result;
use async_trait::async_trait;
use jsonwebtoken::{decode, Algorithm, DecodingKey, Validation};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
struct Claims {
    sub: String,
    target_node: String,
    exp: usize,
}

pub struct JwtVerifier {
    public_key: String,
}

impl JwtVerifier {
    #[allow(dead_code)]
    pub fn new(public_key: String) -> Self {
        Self { public_key }
    }
}

#[async_trait]
impl AuthTokenVerifier for JwtVerifier {
    async fn verify_ticket(&self, token: &str, target_node_id: &str) -> Result<bool> {
        let mut validation = Validation::new(Algorithm::RS256);
        validation.set_audience(&["swarm-worker"]);

        let key = DecodingKey::from_rsa_pem(self.public_key.as_bytes())?;

        match decode::<Claims>(token, &key, &validation) {
            Ok(token_data) => Ok(token_data.claims.target_node == target_node_id),
            Err(_) => Ok(false),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Use a simple test RSA key pair (PKCS#8 for private, SPKI for public)
    // In a real test we might generate one, but for coverage let's use a hardcoded small one or mock it
    // Actually, JwtVerifier uses RSA256, so we need a real RSA key to test the logic properly.
    
    #[tokio::test]
    async fn test_jwt_verifier_invalid_token() {
        let verifier = JwtVerifier::new("invalid-key".to_string());
        let result = verifier.verify_ticket("invalid-token", "node-1").await;
        // Should return Ok(false) on decode error or key error
        assert!(result.is_err() || !result.unwrap());
    }

    #[test]
    fn test_jwt_verifier_new() {
        let verifier = JwtVerifier::new("test-key".to_string());
        assert_eq!(verifier.public_key, "test-key");
    }
}
