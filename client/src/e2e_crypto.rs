//! Client-side E2E encryption for inference requests (ADR-0013).

use monkey_troop_shared::crypto::{
    self, decode_public_key, derive_session_key, E2EChunkEnvelope, E2EEnvelope,
};

/// Session established after ECDH key exchange with a worker.
pub struct E2ESession {
    pub session_key: [u8; 32],
    pub client_public_key_b64: String,
}

/// Create an E2E session by generating an ephemeral keypair and performing ECDH
/// with the worker's public key.
pub fn establish_session(worker_public_key_b64: &str) -> anyhow::Result<E2ESession> {
    let (client_secret, client_pub_b64) = crypto::generate_keypair();
    let worker_pub = decode_public_key(worker_public_key_b64)?;
    let shared_secret = client_secret.diffie_hellman(&worker_pub);
    let session_key = derive_session_key(shared_secret.as_bytes())?;
    Ok(E2ESession {
        session_key,
        client_public_key_b64: client_pub_b64,
    })
}

/// Encrypt a request payload, returning the E2E envelope as a `serde_json::Value`.
pub fn encrypt_request(
    session: &E2ESession,
    plaintext: &[u8],
) -> anyhow::Result<serde_json::Value> {
    let mut payload = crypto::encrypt_payload(&session.session_key, plaintext)?;
    payload.client_public_key = Some(session.client_public_key_b64.clone());
    let envelope = E2EEnvelope { e2e: payload };
    Ok(serde_json::to_value(envelope)?)
}

/// Decrypt a non-streaming response body.
pub fn decrypt_response(session_key: &[u8; 32], body: &[u8]) -> anyhow::Result<Vec<u8>> {
    let envelope: E2EEnvelope = serde_json::from_slice(body)?;
    crypto::decrypt_payload(session_key, &envelope.e2e)
}

/// Decrypt a single SSE data line that contains an encrypted chunk.
pub fn decrypt_sse_chunk(session_key: &[u8; 32], data: &str) -> anyhow::Result<String> {
    let envelope: E2EChunkEnvelope = serde_json::from_str(data)?;
    let plaintext = crypto::decrypt_chunk(session_key, &envelope.e2e)?;
    Ok(String::from_utf8(plaintext)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_establish_session() {
        let (_, worker_pub) = crypto::generate_keypair();
        let session = establish_session(&worker_pub).unwrap();
        assert!(!session.client_public_key_b64.is_empty());
        assert_ne!(session.session_key, [0u8; 32]);
    }

    #[test]
    fn test_encrypt_decrypt_round_trip() -> anyhow::Result<()> {
        let (worker_secret, worker_pub) = crypto::generate_keypair();
        let session = establish_session(&worker_pub)?;

        let plaintext = b"test request payload";
        let encrypted_value = encrypt_request(&session, plaintext)?;

        // Simulate worker decryption
        let envelope: E2EEnvelope = serde_json::from_value(encrypted_value)?;
        let client_pub = decode_public_key(envelope.e2e.client_public_key.as_ref().unwrap())?;
        let shared = worker_secret.diffie_hellman(&client_pub);
        let worker_key = derive_session_key(shared.as_bytes())?;
        let decrypted = crypto::decrypt_payload(&worker_key, &envelope.e2e)?;
        assert_eq!(decrypted, plaintext);
        Ok(())
    }

    #[test]
    fn test_decrypt_response() {
        let key = [42u8; 32];
        let plaintext = b"response data";
        let encrypted = crypto::encrypt_payload(&key, plaintext).unwrap();
        let envelope = E2EEnvelope { e2e: encrypted };
        let body = serde_json::to_vec(&envelope).unwrap();
        let decrypted = decrypt_response(&key, &body).unwrap();
        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn test_decrypt_sse_chunk() {
        let key = [42u8; 32];
        let base_nonce = crypto::generate_base_nonce();
        let plaintext = "chunk data";
        let chunk = crypto::encrypt_chunk(&key, &base_nonce, 0, plaintext.as_bytes()).unwrap();
        let envelope = E2EChunkEnvelope { e2e: chunk };
        let data = serde_json::to_string(&envelope).unwrap();
        let decrypted = decrypt_sse_chunk(&key, &data).unwrap();
        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn test_establish_session_invalid_key() {
        assert!(establish_session("not-valid-key").is_err());
    }
}
