"""Infrastructure layer implementation for RSA key management."""

import os
from pathlib import Path
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from application.security_ports import KeyRepository


class FileSystemKeyRepository(KeyRepository):
    """File system implementation of the KeyRepository."""

    def __init__(self, keys_dir: str = "keys"):
        self.keys_dir = Path(keys_dir)
        self.private_key_file = self.keys_dir / "jwt_private_key.pem"
        self.public_key_file = self.keys_dir / "jwt_public_key.pem"

    def ensure_keys_exist(self) -> None:
        self.keys_dir.mkdir(exist_ok=True)
        if self.private_key_file.exists() and self.public_key_file.exists():
            return

        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
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

        self.private_key_file.write_bytes(private_pem)
        self.public_key_file.write_bytes(public_pem)
        os.chmod(self.private_key_file, 0o400)

    def get_public_key(self) -> str:
        self.ensure_keys_exist()
        return self.public_key_file.read_bytes().decode("utf-8")

    def get_private_key(self) -> bytes:
        self.ensure_keys_exist()
        return self.private_key_file.read_bytes()
