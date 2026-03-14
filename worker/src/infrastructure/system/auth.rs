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

    // A real RSA-2048 public key in SPKI PEM format for use in decoding tests.
    // This key is only for testing and carries no security guarantees.
    const TEST_RSA_PUBLIC_KEY_PEM: &str = "-----BEGIN PUBLIC KEY-----\n\
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvi6xi8a1fb7YIvm19w83\n\
5kfeiOMMr8RfVWYtgRsFIJoi9dRd6GT7HQhVD86gOx55mRdZ7yZ16ITdnuT7dAMY\n\
DjvWBK2p01kBxrgvUNssfDjuJVZbK7PxATXE6sgQGE/q2h5c0pO5c8vtAO09uOC2\n\
CNCAmfd9+/E8kDc7kDJbcBRktVjamKpo1TSOU1xwgImC6Lt+0kh58F51TC5amO8/\n\
xMwf1thQQGuQRyKDZWmaY6v7Ux1xU68VVK3idfX9Zx4rYPH7G6jwwIYGPSQy207d\n\
WkoNZmtZB384i1J3EUo5d+WyodiBCjtBRXeTlkrL4WT2Be641I5LXeRhw9zu4ss/\n\
IQIDAQAB\n\
-----END PUBLIC KEY-----\n";

    #[tokio::test]
    async fn test_jwt_verifier_invalid_key_format() {
        // An obviously invalid RSA PEM key should cause from_rsa_pem to return an error.
        let verifier = JwtVerifier::new("not-a-valid-pem-key".to_string());
        let result = verifier.verify_ticket("any-token", "node-1").await;
        assert!(
            result.is_err(),
            "expected error for invalid RSA public key format"
        );
    }

    #[tokio::test]
    async fn test_jwt_verifier_invalid_token_signature() {
        // Use a syntactically valid RSA public key but an invalid token, which should
        // cause decode to fail and result in Ok(false) from verify_ticket.
        let verifier = JwtVerifier::new(TEST_RSA_PUBLIC_KEY_PEM.to_string());
        let result = verifier.verify_ticket("invalid-token", "node-1").await;
        assert!(
            result.is_ok(),
            "expected Ok result for invalid token with valid key"
        );
        assert!(
            !result.unwrap(),
            "expected verification to fail (false) for invalid token"
        );
    }

    #[test]
    fn test_jwt_verifier_new() {
        let verifier = JwtVerifier::new("test-key".to_string());
        assert_eq!(verifier.public_key, "test-key");
    }
}
