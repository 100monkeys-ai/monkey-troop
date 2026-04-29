use anyhow::{Context, Result};
use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use chacha20poly1305::aead::{Aead, OsRng};
use chacha20poly1305::{ChaCha20Poly1305, KeyInit, Nonce};
use hkdf::Hkdf;
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use x25519_dalek::{PublicKey, StaticSecret};

/// Encrypted payload for non-streaming responses
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptedPayload {
    pub version: u8,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub client_public_key: Option<String>,
    pub nonce: String,
    pub ciphertext: String,
}

/// Encrypted chunk for streaming responses
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptedChunk {
    pub seq: u32,
    pub nonce: String,
    pub ciphertext: String,
}

/// Serde wrapper for encrypted payloads
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct E2EEnvelope {
    pub e2e: EncryptedPayload,
}

/// Serde wrapper for encrypted streaming chunks
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct E2EChunkEnvelope {
    pub e2e: EncryptedChunk,
}

/// Generate a new X25519 keypair, returning (secret, base64-encoded public key)
pub fn generate_keypair() -> (StaticSecret, String) {
    let mut bytes = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut bytes);
    let secret = StaticSecret::from(bytes);
    let public = PublicKey::from(&secret);
    let public_b64 = BASE64.encode(public.as_bytes());
    (secret, public_b64)
}

/// Decode a base64-encoded X25519 public key
pub fn decode_public_key(b64: &str) -> Result<PublicKey> {
    let bytes = BASE64
        .decode(b64)
        .context("Invalid base64 for public key")?;
    let arr: [u8; 32] = bytes
        .try_into()
        .map_err(|v: Vec<u8>| anyhow::anyhow!("Public key must be 32 bytes, got {}", v.len()))?;
    Ok(PublicKey::from(arr))
}

/// Derive a symmetric session key from a shared secret using HKDF-SHA256
pub fn derive_session_key(shared_secret: &[u8; 32]) -> Result<[u8; 32]> {
    let hk = Hkdf::<Sha256>::new(None, shared_secret);
    let mut okm = [0u8; 32];
    hk.expand(b"monkey-troop-e2e-v1", &mut okm)
        .map_err(|e| anyhow::anyhow!("HKDF expansion failed: {e}"))?;
    Ok(okm)
}

/// Generate a random 12-byte nonce
pub fn generate_base_nonce() -> [u8; 12] {
    let mut nonce = [0u8; 12];
    rand::thread_rng().fill_bytes(&mut nonce);
    nonce
}

/// Encrypt a plaintext payload with ChaCha20Poly1305
pub fn encrypt_payload(key: &[u8; 32], plaintext: &[u8]) -> Result<EncryptedPayload> {
    let cipher = ChaCha20Poly1305::new(key.into());
    let nonce_bytes = generate_base_nonce();
    let nonce = Nonce::from_slice(&nonce_bytes);

    let ciphertext = cipher
        .encrypt(nonce, plaintext)
        .map_err(|e| anyhow::anyhow!("Encryption failed: {e}"))?;

    Ok(EncryptedPayload {
        version: 1,
        client_public_key: None,
        nonce: BASE64.encode(nonce_bytes),
        ciphertext: BASE64.encode(ciphertext),
    })
}

/// Decrypt an encrypted payload with ChaCha20Poly1305
pub fn decrypt_payload(key: &[u8; 32], payload: &EncryptedPayload) -> Result<Vec<u8>> {
    let cipher = ChaCha20Poly1305::new(key.into());
    let nonce_bytes = BASE64
        .decode(&payload.nonce)
        .context("Invalid base64 nonce")?;
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ciphertext = BASE64
        .decode(&payload.ciphertext)
        .context("Invalid base64 ciphertext")?;

    cipher
        .decrypt(nonce, ciphertext.as_ref())
        .map_err(|e| anyhow::anyhow!("Decryption failed: {e}"))
}

/// Encrypt a single streaming chunk. Nonce is derived from base_nonce XORed with sequence number.
pub fn encrypt_chunk(
    key: &[u8; 32],
    base_nonce: &[u8; 12],
    seq: u32,
    plaintext: &[u8],
) -> Result<EncryptedChunk> {
    let cipher = ChaCha20Poly1305::new(key.into());
    let mut nonce_bytes = *base_nonce;
    // XOR the last 4 bytes with the sequence number
    let seq_bytes = seq.to_le_bytes();
    for i in 0..4 {
        nonce_bytes[8 + i] ^= seq_bytes[i];
    }
    let nonce = Nonce::from_slice(&nonce_bytes);

    let ciphertext = cipher
        .encrypt(nonce, plaintext)
        .map_err(|e| anyhow::anyhow!("Chunk encryption failed: {e}"))?;

    Ok(EncryptedChunk {
        seq,
        nonce: BASE64.encode(nonce_bytes),
        ciphertext: BASE64.encode(ciphertext),
    })
}

/// Decrypt a single streaming chunk
pub fn decrypt_chunk(key: &[u8; 32], chunk: &EncryptedChunk) -> Result<Vec<u8>> {
    let cipher = ChaCha20Poly1305::new(key.into());
    let nonce_bytes = BASE64
        .decode(&chunk.nonce)
        .context("Invalid base64 nonce in chunk")?;
    let nonce = Nonce::from_slice(&nonce_bytes);
    let ciphertext = BASE64
        .decode(&chunk.ciphertext)
        .context("Invalid base64 ciphertext in chunk")?;

    cipher
        .decrypt(nonce, ciphertext.as_ref())
        .map_err(|e| anyhow::anyhow!("Chunk decryption failed: {e}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_keypair() {
        let (_secret, pub_b64) = generate_keypair();
        assert!(!pub_b64.is_empty());
        assert!(decode_public_key(&pub_b64).is_ok());
    }

    #[test]
    fn test_decode_public_key_invalid() {
        assert!(decode_public_key("not-valid-base64!!!").is_err());
        // Valid base64 but wrong length
        assert!(decode_public_key(&BASE64.encode([0u8; 16])).is_err());
    }

    #[test]
    fn test_derive_session_key_deterministic() -> anyhow::Result<()> {
        let secret = [42u8; 32];
        let k1 = derive_session_key(&secret)?;
        let k2 = derive_session_key(&secret)?;
        assert_eq!(k1, k2);
        Ok(())
    }

    #[test]
    fn test_encrypt_decrypt_payload() {
        let key = [1u8; 32];
        let plaintext = b"hello world";
        let encrypted = encrypt_payload(&key, plaintext).unwrap();
        assert_eq!(encrypted.version, 1);
        let decrypted = decrypt_payload(&key, &encrypted).unwrap();
        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn test_decrypt_payload_wrong_key() {
        let key = [1u8; 32];
        let wrong_key = [2u8; 32];
        let encrypted = encrypt_payload(&key, b"secret").unwrap();
        assert!(decrypt_payload(&wrong_key, &encrypted).is_err());
    }

    #[test]
    fn test_encrypt_decrypt_chunk() {
        let key = [3u8; 32];
        let base_nonce = generate_base_nonce();
        let plaintext = b"chunk data";
        let chunk = encrypt_chunk(&key, &base_nonce, 0, plaintext).unwrap();
        assert_eq!(chunk.seq, 0);
        let decrypted = decrypt_chunk(&key, &chunk).unwrap();
        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn test_chunk_sequence_produces_different_nonces() {
        let key = [4u8; 32];
        let base_nonce = generate_base_nonce();
        let c0 = encrypt_chunk(&key, &base_nonce, 0, b"a").unwrap();
        let c1 = encrypt_chunk(&key, &base_nonce, 1, b"a").unwrap();
        assert_ne!(c0.nonce, c1.nonce);
    }

    #[test]
    fn test_e2e_key_agreement() -> anyhow::Result<()> {
        let (secret_a, pub_a_b64) = generate_keypair();
        let (secret_b, pub_b_b64) = generate_keypair();

        let pub_a = decode_public_key(&pub_a_b64)?;
        let pub_b = decode_public_key(&pub_b_b64)?;

        let shared_a = secret_a.diffie_hellman(&pub_b);
        let shared_b = secret_b.diffie_hellman(&pub_a);

        let key_a = derive_session_key(shared_a.as_bytes())?;
        let key_b = derive_session_key(shared_b.as_bytes())?;

        assert_eq!(key_a, key_b);

        // Full round trip
        let plaintext = b"end-to-end encrypted message";
        let encrypted = encrypt_payload(&key_a, plaintext)?;
        let decrypted = decrypt_payload(&key_b, &encrypted)?;
        assert_eq!(decrypted, plaintext);
        Ok(())
    }

    #[test]
    fn test_envelope_serialization() {
        let key = [5u8; 32];
        let encrypted = encrypt_payload(&key, b"test").unwrap();
        let envelope = E2EEnvelope { e2e: encrypted };
        let json = serde_json::to_string(&envelope).unwrap();
        let deserialized: E2EEnvelope = serde_json::from_str(&json).unwrap();
        let decrypted = decrypt_payload(&key, &deserialized.e2e).unwrap();
        assert_eq!(decrypted, b"test");
    }

    #[test]
    fn test_chunk_envelope_serialization() {
        let key = [6u8; 32];
        let base_nonce = generate_base_nonce();
        let chunk = encrypt_chunk(&key, &base_nonce, 42, b"stream data").unwrap();
        let envelope = E2EChunkEnvelope { e2e: chunk };
        let json = serde_json::to_string(&envelope).unwrap();
        let deserialized: E2EChunkEnvelope = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.e2e.seq, 42);
        let decrypted = decrypt_chunk(&key, &deserialized.e2e).unwrap();
        assert_eq!(decrypted, b"stream data");
    }
}
