use anyhow::{anyhow, Result};
use std::path::PathBuf;

/// Searches for a binary in a hardcoded list of trusted directories.
/// This prevents PATH manipulation attacks by ignoring the environment variable.
pub fn get_secure_binary_path(name: &str) -> Result<PathBuf> {
    let trusted_paths = ["/usr/bin", "/bin", "/usr/local/bin", "/usr/sbin", "/sbin"];

    for dir in trusted_paths {
        let path = PathBuf::from(dir).join(name);
        if path.exists() && path.is_file() {
            return Ok(path);
        }
    }

    Err(anyhow!(
        "Binary '{}' not found in trusted system paths",
        name
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_secure_binary_path_found() {
        // python3 is expected to be in /usr/bin or /bin on most Linux systems
        let result = get_secure_binary_path("python3");
        assert!(result.is_ok());
        let path = result.unwrap();
        assert!(path.to_str().unwrap().contains("python3"));
    }

    #[test]
    fn test_get_secure_binary_path_not_found() {
        let result = get_secure_binary_path("non-existent-binary-12345");
        assert!(result.is_err());
    }
}
