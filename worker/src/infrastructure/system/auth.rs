use async_trait::async_trait;
use crate::application::ports::AuthTokenVerifier;
use anyhow::Result;
use jsonwebtoken::{decode, DecodingKey, Validation, Algorithm};
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
            Ok(token_data) => {
                Ok(token_data.claims.target_node == target_node_id)
            },
            Err(_) => Ok(false),
        }
    }
}
