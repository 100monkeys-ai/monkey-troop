from infrastructure.security.key_repository import FileSystemKeyRepository


def test_file_system_key_repository_ensure_keys_exist(tmp_path):
    keys_dir = tmp_path / "keys"
    repo = FileSystemKeyRepository(keys_dir=str(keys_dir))

    # First time, should generate keys
    repo.ensure_keys_exist()

    assert (keys_dir / "jwt_private_key.pem").exists()
    assert (keys_dir / "jwt_public_key.pem").exists()

    # Second time, should not regenerate
    mod_time = (keys_dir / "jwt_private_key.pem").stat().st_mtime
    repo.ensure_keys_exist()
    assert (keys_dir / "jwt_private_key.pem").stat().st_mtime == mod_time


def test_file_system_key_repository_get_keys(tmp_path):
    keys_dir = tmp_path / "keys"
    repo = FileSystemKeyRepository(keys_dir=str(keys_dir))

    pub_key = repo.get_public_key()
    priv_key = repo.get_private_key()

    assert pub_key.startswith("-----BEGIN PUBLIC KEY-----")
    assert priv_key.startswith(b"-----BEGIN PRIVATE KEY-----")
