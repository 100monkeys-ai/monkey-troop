use super::EngineDriver;
use anyhow::Result;
use monkey_troop_shared::EngineInfo;
use serde::Deserialize;

#[derive(Deserialize)]
struct LMStudioModel {
    id: String,
}

#[derive(Deserialize)]
struct LMStudioModels {
    data: Vec<LMStudioModel>,
}

pub struct LMStudioDriver {
    base_url: String,
}

impl LMStudioDriver {
    pub fn new() -> Self {
        Self {
            base_url: "http://localhost:1234".to_string(),
        }
    }

    #[cfg(test)]
    fn with_base_url(base_url: String) -> Self {
        Self { base_url }
    }
}

impl EngineDriver for LMStudioDriver {
    fn detect(&self) -> Result<bool> {
        let client = reqwest::blocking::Client::new();
        let response = client
            .get(format!("{}/v1/models", self.base_url))
            .timeout(std::time::Duration::from_secs(2))
            .send();

        match response {
            Ok(res) => Ok(res.status().is_success()),
            Err(_) => Ok(false),
        }
    }

    fn get_info(&self) -> Result<EngineInfo> {
        Ok(EngineInfo {
            engine_type: "lmstudio".to_string(),
            version: "unknown".to_string(),
            port: 1234,
        })
    }

    fn get_models(&self) -> Result<Vec<String>> {
        let client = reqwest::blocking::Client::new();
        let response = client.get(format!("{}/v1/models", self.base_url)).send()?;

        let models_info: LMStudioModels = response.json()?;

        Ok(models_info.data.into_iter().map(|m| m.id).collect())
    }

    fn get_base_url(&self) -> String {
        self.base_url.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use httpmock::MockServer;
    use serde_json::json;

    #[test]
    fn test_lmstudio_detect_success() {
        let server = MockServer::start();

        let mock = server.mock(|when, then| {
            when.method("GET").path("/v1/models");
            then.status(200);
        });

        let driver = LMStudioDriver::with_base_url(server.base_url());

        let result = driver.detect();
        assert!(result.is_ok());
        assert!(result.unwrap());

        mock.assert();
    }

    #[test]
    fn test_lmstudio_detect_network_error() {
        // Use an invalid/unreachable URL to trigger a network-level error
        let driver = LMStudioDriver::with_base_url("http://127.0.0.1:0".to_string());

        let result = driver.detect();
        assert!(result.is_ok());
        assert!(!result.unwrap());
    }

    #[test]
    fn test_lmstudio_detect_failure() {
        let server = MockServer::start();

        let mock = server.mock(|when, then| {
            when.method("GET").path("/v1/models");
            then.status(500);
        });

        let driver = LMStudioDriver::with_base_url(server.base_url());

        let result = driver.detect();
        assert!(result.is_ok());
        assert!(!result.unwrap());

        mock.assert();
    }

    #[test]
    fn test_lmstudio_get_info() {
        let driver = LMStudioDriver::new();
        let info = driver.get_info().unwrap();

        assert_eq!(info.engine_type, "lmstudio");
        assert_eq!(info.version, "unknown");
        assert_eq!(info.port, 1234);
    }

    #[test]
    fn test_lmstudio_get_models_success() {
        let server = MockServer::start();

        let mock_response = json!({
            "data": [
                { "id": "model-1", "object": "model" },
                { "id": "model-2", "object": "model" }
            ]
        });

        let mock = server.mock(|when, then| {
            when.method("GET").path("/v1/models");
            then.status(200)
                .header("content-type", "application/json")
                .json_body(mock_response);
        });

        let driver = LMStudioDriver::with_base_url(server.base_url());

        let models = driver.get_models().unwrap();
        assert_eq!(models.len(), 2);
        assert_eq!(models[0], "model-1");
        assert_eq!(models[1], "model-2");

        mock.assert();
    }

    #[test]
    fn test_lmstudio_get_models_invalid_json() {
        let server = MockServer::start();

        let mock = server.mock(|when, then| {
            when.method("GET").path("/v1/models");
            then.status(200)
                .header("content-type", "application/json")
                .body("not valid json");
        });

        let driver = LMStudioDriver::with_base_url(server.base_url());

        let result = driver.get_models();
        assert!(result.is_err());

        mock.assert();
    }

    #[test]
    fn test_lmstudio_get_models_failure() {
        let server = MockServer::start();

        let mock = server.mock(|when, then| {
            when.method("GET").path("/v1/models");
            then.status(500);
        });

        let driver = LMStudioDriver::with_base_url(server.base_url());

        let result = driver.get_models();
        assert!(result.is_err());

        mock.assert();
    }

    #[test]
    fn test_lmstudio_get_base_url() {
        let driver = LMStudioDriver::new();
        assert_eq!(driver.get_base_url(), "http://localhost:1234");

        let driver2 = LMStudioDriver::with_base_url("http://test:4321".to_string());
        assert_eq!(driver2.get_base_url(), "http://test:4321");
    }
}
