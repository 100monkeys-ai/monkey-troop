use super::EngineDriver;
use anyhow::Result;
use monkey_troop_shared::EngineInfo;
use serde::Deserialize;
use std::env;

#[derive(Deserialize)]
struct OllamaVersion {
    version: String,
}

#[derive(Deserialize)]
struct OllamaModels {
    models: Vec<OllamaModel>,
}

#[derive(Deserialize)]
struct OllamaModel {
    name: String,
}

pub struct OllamaDriver {
    base_url: String,
}

impl OllamaDriver {
    pub fn new() -> Self {
        let base_url =
            env::var("OLLAMA_HOST").unwrap_or_else(|_| "http://localhost:11434".to_string());

        Self { base_url }
    }
}

impl EngineDriver for OllamaDriver {
    fn detect(&self) -> Result<bool> {
        // Try to hit the version endpoint
        let client = reqwest::blocking::Client::new();
        let response = client
            .get(format!("{}/api/version", self.base_url))
            .timeout(std::time::Duration::from_secs(2))
            .send();

        match response {
            Ok(resp) => Ok(resp.status().is_success()),
            Err(_) => Ok(false),
        }
    }

    fn get_info(&self) -> Result<EngineInfo> {
        let client = reqwest::blocking::Client::new();
        let response = client
            .get(format!("{}/api/version", self.base_url))
            .send()?
            .error_for_status()?;

        let version_info: OllamaVersion = response.json()?;

        Ok(EngineInfo {
            engine_type: "ollama".to_string(),
            version: version_info.version,
            port: 11434, // Default Ollama port
        })
    }

    fn get_models(&self) -> Result<Vec<String>> {
        let client = reqwest::blocking::Client::new();
        let response = client
            .get(format!("{}/api/tags", self.base_url))
            .send()?
            .error_for_status()?;

        let models_info: OllamaModels = response.json()?;

        Ok(models_info.models.into_iter().map(|m| m.name).collect())
    }

    fn get_base_url(&self) -> String {
        self.base_url.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use httpmock::MockServer;

    fn create_driver(server: &MockServer) -> OllamaDriver {
        OllamaDriver {
            base_url: server.base_url(),
        }
    }

    #[test]
    fn test_detect_success() {
        let server = MockServer::start();
        let mock = server.mock(|when, then| {
            when.method(httpmock::Method::GET).path("/api/version");
            then.status(200);
        });

        let driver = create_driver(&server);
        let result = driver.detect();

        mock.assert();
        assert!(result.is_ok());
        assert!(result.unwrap());
    }

    #[test]
    fn test_detect_failure() {
        let server = MockServer::start();
        let mock = server.mock(|when, then| {
            when.method(httpmock::Method::GET).path("/api/version");
            then.status(500);
        });

        let driver = create_driver(&server);
        let result = driver.detect();

        mock.assert();
        assert!(result.is_ok());
        assert!(!result.unwrap());
    }

    #[test]
    fn test_detect_network_error() {
        // Point at a port where nothing is listening
        let driver = OllamaDriver {
            base_url: "http://127.0.0.1:1".to_string(),
        };
        let result = driver.detect();
        assert!(result.is_ok());
        assert!(!result.unwrap());
    }

    #[test]
    fn test_get_info_success() {
        let server = MockServer::start();
        let mock = server.mock(|when, then| {
            when.method(httpmock::Method::GET).path("/api/version");
            then.status(200)
                .header("content-type", "application/json")
                .body(r#"{"version": "0.1.27"}"#);
        });

        let driver = create_driver(&server);
        let result = driver.get_info();

        mock.assert();
        assert!(result.is_ok());
        let info = result.unwrap();
        assert_eq!(info.engine_type, "ollama");
        assert_eq!(info.version, "0.1.27");
        assert_eq!(info.port, 11434);
    }

    #[test]
    fn test_get_info_failure() {
        let server = MockServer::start();
        let mock = server.mock(|when, then| {
            when.method(httpmock::Method::GET).path("/api/version");
            then.status(500);
        });

        let driver = create_driver(&server);
        let result = driver.get_info();

        mock.assert();
        assert!(result.is_err());
    }

    #[test]
    fn test_get_info_failure_with_valid_json_body() {
        let server = MockServer::start();
        let mock = server.mock(|when, then| {
            when.method(httpmock::Method::GET).path("/api/version");
            then.status(500)
                .header("content-type", "application/json")
                .body(r#"{"version": "0.1.27"}"#);
        });

        let driver = create_driver(&server);
        let result = driver.get_info();

        mock.assert();
        assert!(result.is_err());
    }

    #[test]
    fn test_get_models_success() {
        let server = MockServer::start();
        let mock = server.mock(|when, then| {
            when.method(httpmock::Method::GET).path("/api/tags");
            then.status(200)
                .header("content-type", "application/json")
                .body(r#"{"models": [{"name": "llama3:8b"}, {"name": "mistral"}]}"#);
        });

        let driver = create_driver(&server);
        let result = driver.get_models();

        mock.assert();
        assert!(result.is_ok());
        let models = result.unwrap();
        assert_eq!(models.len(), 2);
        assert_eq!(models[0], "llama3:8b");
        assert_eq!(models[1], "mistral");
    }

    #[test]
    fn test_get_models_failure() {
        let server = MockServer::start();
        let mock = server.mock(|when, then| {
            when.method(httpmock::Method::GET).path("/api/tags");
            then.status(500);
        });

        let driver = create_driver(&server);
        let result = driver.get_models();

        mock.assert();
        assert!(result.is_err());
    }

    #[test]
    fn test_get_models_failure_with_valid_json_body() {
        let server = MockServer::start();
        let mock = server.mock(|when, then| {
            when.method(httpmock::Method::GET).path("/api/tags");
            then.status(500)
                .header("content-type", "application/json")
                .body(r#"{"models": [{"name": "llama3:8b"}]}"#);
        });

        let driver = create_driver(&server);
        let result = driver.get_models();

        mock.assert();
        assert!(result.is_err());
    }

    #[test]
    fn test_get_base_url() {
        let driver = OllamaDriver {
            base_url: "http://test-url:11434".to_string(),
        };
        assert_eq!(driver.get_base_url(), "http://test-url:11434");
    }
}
