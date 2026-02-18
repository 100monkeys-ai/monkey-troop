"""Cryptographic utilities for JWT signing and key management."""

import os
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

# Key storage paths
KEYS_DIR = Path("keys")
PRIVATE_KEY_FILE = KEYS_DIR / "jwt_private_key.pem"
PUBLIC_KEY_FILE = KEYS_DIR / "jwt_public_key.pem"


def generate_rsa_keypair(key_size: int = 2048) -> tuple[bytes, bytes]:
    """
    Generate RSA keypair for JWT signing.

    Args:
        key_size: RSA key size (default 2048 bits)

    Returns:
        Tuple of (private_key_pem, public_key_pem) as bytes
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=key_size, backend=default_backend()
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    return private_pem, public_pem


def ensure_keys_exist() -> None:
    """
    Ensure RSA keypair exists. Generate if missing.
    Keys are stored in the keys/ directory.
    """
    KEYS_DIR.mkdir(exist_ok=True)

    if PRIVATE_KEY_FILE.exists() and PUBLIC_KEY_FILE.exists():
        print("🔑 RSA keys found")
        return

    print("🔑 Generating RSA keypair...")
    private_pem, public_pem = generate_rsa_keypair()

    # Write keys to files with restricted permissions
    PRIVATE_KEY_FILE.write_bytes(private_pem)
    PUBLIC_KEY_FILE.write_bytes(public_pem)

    # Restrict private key permissions (owner read-only)
    os.chmod(PRIVATE_KEY_FILE, 0o400)

    print(f"✓ Private key saved to {PRIVATE_KEY_FILE}")
    print(f"✓ Public key saved to {PUBLIC_KEY_FILE}")


def load_private_key() -> bytes:
    """Load private key from file."""
    if not PRIVATE_KEY_FILE.exists():
        ensure_keys_exist()
    return PRIVATE_KEY_FILE.read_bytes()


def load_public_key() -> bytes:
    """Load public key from file."""
    if not PUBLIC_KEY_FILE.exists():
        ensure_keys_exist()
    return PUBLIC_KEY_FILE.read_bytes()


def get_public_key_string() -> str:
    """Get public key as string for distribution."""
    return load_public_key().decode("utf-8")
