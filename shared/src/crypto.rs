//! End-to-End Encryption primitives for inference data (ADR-0013).
//!
//! Uses X25519 for key agreement and ChaCha20-Poly1305 for symmetric encryption.

use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use chacha20poly1305::aead::{Aead, KeyInit};
use chacha20poly1305::{ChaCha20Poly1305, Nonce};
use hkdf::Hkdf;
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use x25519_dalek::{PublicKey, StaticSecret};

pub const E2E_VERSION: u32 = 1;
const HKDF_INFO: &[u8] = b"monkey-troop-e2e-v1";

/// Encrypted payload envelope for requests (includes client's ephemeral public key).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptedPayload {
    pub version: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub client_public_key: Option<String>,
    pub nonce: String,
    pub ciphertext: String,
}

/// Encrypted chunk for streaming SSE responses.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptedChunk {
    pub seq: u32,
    pub nonce: String,
    pub ciphertext: String,
}

/// E2E envelope wrapper — detected by presence of `e2e` field in JSON.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct E2EEnvelope {
    pub e2e: EncryptedPayload,
}

/// E2E streaming chunk envelope.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct E2EChunkEnvelope {
    pub e2e: EncryptedChunk,
}

/// Generate a new X25519 keypair. Returns (secret, base64-encoded public key).
pub fn generate_keypair() -> (StaticSecret, String) {
    let secret = StaticSecret::random_from_rng(OsRng);
    let public = PublicKey::from(&secret);
    let public_b64 = BASE64.encode(public.as_bytes());
    (secret, public_b64)
}

/// Decode a base64-encoded X25519 public key.
pub fn decode_public_key(b64: &str) -> anyhow::Result<PublicKey> {
    let bytes = BASE64.decode(b64)?;
    let arr: [u8; 32] = bytes
        .try_into()
        .map_err(|_| anyhow::anyhow!("Invalid public key length"))?;
    Ok(PublicKey::from(arr))
}

/// Perform ECDH and derive a 32-byte symmetric session key via HKDF-SHA256.
pub fn derive_session_key(shared_secret: &[u8; 32]) -> [u8; 32] {
    let hk = Hkdf::<Sha256>::new(None, shared_secret);
    let mut okm = [0u8; 32];
    hk.expand(HKDF_INFO, &mut okm)
        .expect("HKDF expand should not fail for 32-byte output");
    okm
}

/// Encrypt plaintext with ChaCha20-Poly1305 using the given key.
/// Returns an EncryptedPayload with a random nonce. `client_public_key` is set by the caller.
pub fn encrypt_payload(key: &[u8; 32], plaintext: &[u8]) -> anyhow::Result<EncryptedPayload> {
    let cipher = ChaCha20Poly1305::new(key.into());
    let nonce_bytes = generate_nonce();
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ciphertext = cipher
        .encrypt(nonce, plaintext)
        .map_err(|e| anyhow::anyhow!("Encryption failed: {}", e))?;

    Ok(EncryptedPayload {
        version: E2E_VERSION,
        client_public_key: None,
        nonce: BASE64.encode(nonce_bytes),
        ciphertext: BASE64.encode(ciphertext),
    })
}

/// Decrypt an EncryptedPayload with ChaCha20-Poly1305.
pub fn decrypt_payload(key: &[u8; 32], payload: &EncryptedPayload) -> anyhow::Result<Vec<u8>> {
    let cipher = ChaCha20Poly1305::new(key.into());
    let nonce_bytes = BASE64.decode(&payload.nonce)?;
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ciphertext = BASE64.decode(&payload.ciphertext)?;
    cipher
        .decrypt(nonce, ciphertext.as_ref())
        .map_err(|e| anyhow::anyhow!("Decryption failed: {}", e))
}

/// Compute nonce for a given sequence number by XOR-ing the last 4 bytes of base_nonce.
pub fn nonce_for_seq(base_nonce: &[u8; 12], seq: u32) -> [u8; 12] {
    let mut nonce = *base_nonce;
    let seq_bytes = seq.to_le_bytes();
    for i in 0..4 {
        nonce[8 + i] ^= seq_bytes[i];
    }
    nonce
}

/// Encrypt a single streaming chunk.
pub fn encrypt_chunk(
    key: &[u8; 32],
    base_nonce: &[u8; 12],
    seq: u32,
    plaintext: &[u8],
) -> anyhow::Result<EncryptedChunk> {
    let cipher = ChaCha20Poly1305::new(key.into());
    let nonce_bytes = nonce_for_seq(base_nonce, seq);
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ciphertext = cipher
        .encrypt(nonce, plaintext)
        .map_err(|e| anyhow::anyhow!("Chunk encryption failed: {}", e))?;

    Ok(EncryptedChunk {
        seq,
        nonce: BASE64.encode(nonce_bytes),
        ciphertext: BASE64.encode(ciphertext),
    })
}

/// Decrypt a single streaming chunk.
pub fn decrypt_chunk(key: &[u8; 32], chunk: &EncryptedChunk) -> anyhow::Result<Vec<u8>> {
    let cipher = ChaCha20Poly1305::new(key.into());
    let nonce_bytes = BASE64.decode(&chunk.nonce)?;
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ciphertext = BASE64.decode(&chunk.ciphertext)?;
    cipher
        .decrypt(nonce, ciphertext.as_ref())
        .map_err(|e| anyhow::anyhow!("Chunk decryption failed: {}", e))
}

fn generate_nonce() -> [u8; 12] {
    let mut nonce = [0u8; 12];
    use rand::RngCore;
    OsRng.fill_bytes(&mut nonce);
    nonce
}

/// Generate a random 12-byte base nonce for streaming.
pub fn generate_base_nonce() -> [u8; 12] {
    generate_nonce()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_round_trip_encrypt_decrypt() {
        let key = [42u8; 32];
        let plaintext = b"Hello, encrypted world!";
        let payload = encrypt_payload(&key, plaintext).unwrap();
        let decrypted = decrypt_payload(&key, &payload).unwrap();
        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn test_wrong_key_fails() {
        let key = [42u8; 32];
        let wrong_key = [99u8; 32];
        let plaintext = b"secret data";
        let payload = encrypt_payload(&key, plaintext).unwrap();
        assert!(decrypt_payload(&wrong_key, &payload).is_err());
    }

    #[test]
    fn test_keypair_and_ecdh() {
        let (secret_a, pub_a_b64) = generate_keypair();
        let (secret_b, pub_b_b64) = generate_keypair();

        let pub_a = decode_public_key(&pub_a_b64).unwrap();
        let pub_b = decode_public_key(&pub_b_b64).unwrap();

        let shared_a = secret_a.diffie_hellman(&pub_b);
        let shared_b = secret_b.diffie_hellman(&pub_a);

        let key_a = derive_session_key(shared_a.as_bytes());
        let key_b = derive_session_key(shared_b.as_bytes());
        assert_eq!(key_a, key_b);
    }

    #[test]
    fn test_hkdf_determinism() {
        let secret = [7u8; 32];
        let k1 = derive_session_key(&secret);
        let k2 = derive_session_key(&secret);
        assert_eq!(k1, k2);
    }

    #[test]
    fn test_nonce_for_seq_uniqueness() {
        let base = [1u8; 12];
        let n0 = nonce_for_seq(&base, 0);
        let n1 = nonce_for_seq(&base, 1);
        let n2 = nonce_for_seq(&base, 2);
        assert_eq!(n0, base); // XOR with 0 is identity
        assert_ne!(n1, n0);
        assert_ne!(n2, n1);
    }

    #[test]
    fn test_stream_chunk_round_trip() {
        let key = [55u8; 32];
        let base_nonce = generate_base_nonce();
        let plaintext = b"streaming chunk data";

        let chunk = encrypt_chunk(&key, &base_nonce, 0, plaintext).unwrap();
        let decrypted = decrypt_chunk(&key, &chunk).unwrap();
        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn test_stream_multiple_chunks() {
        let key = [55u8; 32];
        let base_nonce = generate_base_nonce();

        for seq in 0..10 {
            let data = format!("chunk {seq}");
            let chunk = encrypt_chunk(&key, &base_nonce, seq, data.as_bytes()).unwrap();
            let decrypted = decrypt_chunk(&key, &chunk).unwrap();
            assert_eq!(decrypted, data.as_bytes());
        }
    }

    #[test]
    fn test_full_e2e_flow() {
        // Simulate client -> worker flow
        let (worker_secret, worker_pub_b64) = generate_keypair();
        let (client_secret, client_pub_b64) = generate_keypair();

        let worker_pub = decode_public_key(&worker_pub_b64).unwrap();
        let client_pub = decode_public_key(&client_pub_b64).unwrap();
        let _ = client_pub; // used indirectly via b64

        // Client side: encrypt request
        let shared_client = client_secret.diffie_hellman(&worker_pub);
        let session_key = derive_session_key(shared_client.as_bytes());
        let request = b"{\"model\":\"llama3\",\"messages\":[]}";
        let mut payload = encrypt_payload(&session_key, request).unwrap();
        payload.client_public_key = Some(client_pub_b64);

        // Worker side: decrypt request
        let client_pub_decoded =
            decode_public_key(payload.client_public_key.as_ref().unwrap()).unwrap();
        let shared_worker = worker_secret.diffie_hellman(&client_pub_decoded);
        let worker_session_key = derive_session_key(shared_worker.as_bytes());
        let decrypted = decrypt_payload(&worker_session_key, &payload).unwrap();
        assert_eq!(decrypted, request);

        // Worker side: encrypt response
        let response = b"{\"choices\":[{\"message\":{\"content\":\"Hello!\"}}]}";
        let response_payload = encrypt_payload(&worker_session_key, response).unwrap();

        // Client side: decrypt response
        let decrypted_response = decrypt_payload(&session_key, &response_payload).unwrap();
        assert_eq!(decrypted_response, response);
    }

    #[test]
    fn test_e2e_envelope_serde() {
        let key = [42u8; 32];
        let payload = encrypt_payload(&key, b"test").unwrap();
        let envelope = E2EEnvelope { e2e: payload };
        let json = serde_json::to_string(&envelope).unwrap();
        let parsed: E2EEnvelope = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed.e2e.version, E2E_VERSION);
    }

    #[test]
    fn test_decode_invalid_public_key() {
        assert!(decode_public_key("not-valid-base64!!!").is_err());
        assert!(decode_public_key(&BASE64.encode([0u8; 16])).is_err()); // wrong length
    }
}
