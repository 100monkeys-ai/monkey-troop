use crate::application::ports::E2EDecryptor;
use monkey_troop_shared::crypto;

pub struct X25519Decryptor {
    secret: x25519_dalek::StaticSecret,
    public_key_b64: String,
}

impl X25519Decryptor {
    pub fn new() -> Self {
        let (secret, public_key_b64) = crypto::generate_keypair();
        Self {
            secret,
            public_key_b64,
        }
    }
}

impl E2EDecryptor for X25519Decryptor {
    fn public_key_b64(&self) -> &str {
        &self.public_key_b64
    }

    fn derive_session_key(&self, client_public_key_b64: &str) -> anyhow::Result<[u8; 32]> {
        let client_pub = crypto::decode_public_key(client_public_key_b64)?;
        let shared_secret = self.secret.diffie_hellman(&client_pub);
        Ok(crypto::derive_session_key(shared_secret.as_bytes()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_generates_valid_keypair() {
        let decryptor = X25519Decryptor::new();
        let key = decryptor.public_key_b64();
        assert!(!key.is_empty());
        // Verify it's valid base64 that decodes to 32 bytes
        assert!(crypto::decode_public_key(key).is_ok());
    }

    #[test]
    fn test_derive_session_key_matches() -> anyhow::Result<()> {
        let worker = X25519Decryptor::new();
        let (client_secret, client_pub_b64) = crypto::generate_keypair();

        // Worker derives key from client's public key
        let worker_key = worker.derive_session_key(&client_pub_b64)?;

        // Client derives key from worker's public key
        let worker_pub = crypto::decode_public_key(worker.public_key_b64())?;
        let shared = client_secret.diffie_hellman(&worker_pub);
        let client_key = crypto::derive_session_key(shared.as_bytes());

        assert_eq!(worker_key, client_key);
        Ok(())
    }

    #[test]
    fn test_derive_session_key_invalid_key() {
        let worker = X25519Decryptor::new();
        assert!(worker.derive_session_key("invalid-base64!!!").is_err());
    }
}
