use crate::application::ports::InferenceEngine;
use crate::domain::inference::{
    ChatMessage, ChatMessageDelta, InferenceChoice, InferenceResponse, StreamingChoice,
    StreamingChunk, TokenUsage,
};
use crate::domain::models::{EngineType, Model};
use anyhow::Result;
use async_trait::async_trait;
use bytes::BytesMut;
use futures::stream::{self, StreamExt};
use futures::Stream;
use serde::{Deserialize, Serialize};
use std::env;
use std::pin::Pin;

#[derive(Deserialize)]
struct OllamaModels {
    models: Vec<OllamaModel>,
}

#[derive(Deserialize)]
struct OllamaModel {
    name: String,
    digest: String,
    size: u64,
}

#[derive(Serialize)]
struct OllamaChatRequest {
    model: String,
    messages: Vec<OllamaChatMessage>,
    stream: bool,
}

#[derive(Serialize)]
struct OllamaChatMessage {
    role: String,
    content: String,
}

impl From<&ChatMessage> for OllamaChatMessage {
    fn from(msg: &ChatMessage) -> Self {
        Self {
            role: msg.role.clone(),
            content: msg.content.clone(),
        }
    }
}

#[derive(Deserialize)]
struct OllamaChatResponse {
    message: OllamaResponseMessage,
    #[serde(default)]
    prompt_eval_count: Option<u32>,
    #[serde(default)]
    eval_count: Option<u32>,
}

#[derive(Deserialize)]
struct OllamaResponseMessage {
    role: String,
    content: String,
}

#[derive(Deserialize)]
struct OllamaStreamChunk {
    message: OllamaResponseMessage,
    done: bool,
}

fn generate_completion_id() -> String {
    format!("chatcmpl-{}", uuid::Uuid::new_v4())
}

fn current_unix_timestamp() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

pub struct OllamaEngine {
    base_url: String,
    client: reqwest::Client,
}

impl OllamaEngine {
    pub fn new() -> Self {
        let base_url =
            env::var("OLLAMA_HOST").unwrap_or_else(|_| "http://localhost:11434".to_string());
        Self {
            base_url,
            client: reqwest::Client::new(),
        }
    }
}

#[async_trait]
impl InferenceEngine for OllamaEngine {
    async fn get_models(&self) -> Result<Vec<Model>> {
        let response = self
            .client
            .get(format!("{}/api/tags", self.base_url))
            .send()
            .await?;

        let models_info: OllamaModels = response.json().await?;

        Ok(models_info
            .models
            .into_iter()
            .map(|m| Model {
                id: m.name,
                content_hash: m.digest,
                size_bytes: m.size,
                engine_type: EngineType::Ollama,
            })
            .collect())
    }

    async fn is_healthy(&self) -> bool {
        let response = self
            .client
            .get(format!("{}/api/version", self.base_url))
            .timeout(std::time::Duration::from_secs(2))
            .send()
            .await;

        match response {
            Ok(resp) => resp.status().is_success(),
            Err(_) => false,
        }
    }

    async fn chat(&self, model: &str, messages: Vec<ChatMessage>) -> Result<InferenceResponse> {
        let request = OllamaChatRequest {
            model: model.to_string(),
            messages: messages.iter().map(OllamaChatMessage::from).collect(),
            stream: false,
        };

        let response = self
            .client
            .post(format!("{}/api/chat", self.base_url))
            .json(&request)
            .send()
            .await?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            anyhow::bail!("Ollama chat failed with status {status}: {body}");
        }

        let ollama_resp: OllamaChatResponse = response.json().await?;
        let prompt_tokens = ollama_resp.prompt_eval_count.unwrap_or(0);
        let completion_tokens = ollama_resp.eval_count.unwrap_or(0);

        Ok(InferenceResponse {
            id: generate_completion_id(),
            object: "chat.completion".to_string(),
            created: current_unix_timestamp(),
            model: model.to_string(),
            choices: vec![InferenceChoice {
                index: 0,
                message: ChatMessage {
                    role: ollama_resp.message.role,
                    content: ollama_resp.message.content,
                },
                finish_reason: "stop".to_string(),
            }],
            usage: TokenUsage {
                prompt_tokens,
                completion_tokens,
                total_tokens: prompt_tokens + completion_tokens,
            },
        })
    }

    async fn chat_stream(
        &self,
        model: &str,
        messages: Vec<ChatMessage>,
    ) -> Result<Pin<Box<dyn Stream<Item = Result<StreamingChunk>> + Send>>> {
        let request = OllamaChatRequest {
            model: model.to_string(),
            messages: messages.iter().map(OllamaChatMessage::from).collect(),
            stream: true,
        };

        let response = self
            .client
            .post(format!("{}/api/chat", self.base_url))
            .json(&request)
            .send()
            .await?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            anyhow::bail!("Ollama chat_stream failed with status {status}: {body}");
        }

        let completion_id = generate_completion_id();
        let created = current_unix_timestamp();
        let model_owned = model.to_string();
        let byte_stream = response.bytes_stream();

        let chunk_stream = stream::unfold(
            (
                byte_stream,
                BytesMut::new(),
                completion_id,
                created,
                model_owned,
            ),
            |(mut byte_stream, mut buffer, completion_id, created, model_name)| async move {
                loop {
                    if let Some(pos) = buffer.iter().position(|&b| b == b'\n') {
                        let line_bytes = buffer.split_to(pos + 1);
                        let line = String::from_utf8_lossy(&line_bytes).trim().to_string();
                        if line.is_empty() {
                            continue;
                        }
                        match serde_json::from_str::<OllamaStreamChunk>(&line) {
                            Ok(ollama_chunk) => {
                                let finish_reason = if ollama_chunk.done {
                                    Some("stop".to_string())
                                } else {
                                    None
                                };
                                let chunk = StreamingChunk {
                                    id: completion_id.clone(),
                                    object: "chat.completion.chunk".to_string(),
                                    created,
                                    model: model_name.clone(),
                                    choices: vec![StreamingChoice {
                                        index: 0,
                                        delta: ChatMessageDelta {
                                            role: if ollama_chunk.done {
                                                None
                                            } else {
                                                Some(ollama_chunk.message.role)
                                            },
                                            content: if ollama_chunk.done {
                                                None
                                            } else {
                                                Some(ollama_chunk.message.content)
                                            },
                                        },
                                        finish_reason,
                                    }],
                                };
                                return Some((
                                    Ok(chunk),
                                    (byte_stream, buffer, completion_id, created, model_name),
                                ));
                            }
                            Err(e) => {
                                return Some((
                                    Err(anyhow::anyhow!("Failed to parse stream chunk: {e}")),
                                    (byte_stream, buffer, completion_id, created, model_name),
                                ));
                            }
                        }
                    }

                    match byte_stream.next().await {
                        Some(Ok(bytes)) => {
                            buffer.extend_from_slice(&bytes);
                        }
                        Some(Err(e)) => {
                            return Some((
                                Err(anyhow::anyhow!("Stream read error: {e}")),
                                (byte_stream, buffer, completion_id, created, model_name),
                            ));
                        }
                        None => {
                            if !buffer.is_empty() {
                                let remaining = String::from_utf8_lossy(&buffer).trim().to_string();
                                buffer.clear();
                                if !remaining.is_empty() {
                                    match serde_json::from_str::<OllamaStreamChunk>(&remaining) {
                                        Ok(ollama_chunk) => {
                                            let finish_reason = if ollama_chunk.done {
                                                Some("stop".to_string())
                                            } else {
                                                None
                                            };
                                            let chunk = StreamingChunk {
                                                id: completion_id.clone(),
                                                object: "chat.completion.chunk".to_string(),
                                                created,
                                                model: model_name.clone(),
                                                choices: vec![StreamingChoice {
                                                    index: 0,
                                                    delta: ChatMessageDelta {
                                                        role: if ollama_chunk.done {
                                                            None
                                                        } else {
                                                            Some(ollama_chunk.message.role)
                                                        },
                                                        content: if ollama_chunk.done {
                                                            None
                                                        } else {
                                                            Some(ollama_chunk.message.content)
                                                        },
                                                    },
                                                    finish_reason,
                                                }],
                                            };
                                            return Some((
                                                Ok(chunk),
                                                (
                                                    byte_stream,
                                                    buffer,
                                                    completion_id,
                                                    created,
                                                    model_name,
                                                ),
                                            ));
                                        }
                                        Err(e) => {
                                            return Some((
                                                Err(anyhow::anyhow!(
                                                    "Failed to parse final chunk: {e}"
                                                )),
                                                (
                                                    byte_stream,
                                                    buffer,
                                                    completion_id,
                                                    created,
                                                    model_name,
                                                ),
                                            ));
                                        }
                                    }
                                }
                            }
                            return None;
                        }
                    }
                }
            },
        );

        Ok(Box::pin(chunk_stream))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use futures::StreamExt;
    use httpmock::prelude::*;
    use serde_json::json;

    #[tokio::test]
    async fn test_ollama_get_models() {
        let server = MockServer::start();
        let engine = OllamaEngine {
            base_url: server.base_url(),
            client: reqwest::Client::new(),
        };

        let _mock = server.mock(|when, then| {
            when.method(GET).path("/api/tags");
            then.status(200)
                .header("content-type", "application/json")
                .json_body(json!({
                    "models": [
                        { "name": "llama3:8b", "digest": "sha256:aaa111", "size": 4_000_000_000_u64 },
                        { "name": "mistral:latest", "digest": "sha256:bbb222", "size": 7_000_000_000_u64 }
                    ]
                }));
        });

        let models = engine.get_models().await.unwrap();
        assert_eq!(models.len(), 2);
        assert_eq!(models[0].id, "llama3:8b");
        assert_eq!(models[0].content_hash, "sha256:aaa111");
        assert_eq!(models[0].size_bytes, 4_000_000_000);
        assert_eq!(models[1].id, "mistral:latest");
        assert_eq!(models[1].content_hash, "sha256:bbb222");
        assert_eq!(models[1].size_bytes, 7_000_000_000);
    }

    #[tokio::test]
    async fn test_ollama_health_check() {
        let server = MockServer::start();
        let engine = OllamaEngine {
            base_url: server.base_url(),
            client: reqwest::Client::new(),
        };

        let mut mock_success = server.mock(|when, then| {
            when.method(GET).path("/api/version");
            then.status(200);
        });

        assert!(engine.is_healthy().await);
        mock_success.assert();
        mock_success.delete();

        let _mock_fail = server.mock(|when, then| {
            when.method(GET).path("/api/version");
            then.status(500);
        });

        assert!(!engine.is_healthy().await);
    }

    #[tokio::test]
    async fn test_chat_success() {
        let server = MockServer::start();
        let engine = OllamaEngine {
            base_url: server.base_url(),
            client: reqwest::Client::new(),
        };

        let _mock = server.mock(|when, then| {
            when.method(POST).path("/api/chat");
            then.status(200)
                .header("content-type", "application/json")
                .json_body(json!({
                    "message": { "role": "assistant", "content": "Hello there!" },
                    "prompt_eval_count": 10,
                    "eval_count": 5
                }));
        });

        let messages = vec![ChatMessage {
            role: "user".to_string(),
            content: "Hi".to_string(),
        }];
        let resp = engine.chat("llama3:8b", messages).await.unwrap();

        assert_eq!(resp.object, "chat.completion");
        assert_eq!(resp.model, "llama3:8b");
        assert_eq!(resp.choices.len(), 1);
        assert_eq!(resp.choices[0].message.content, "Hello there!");
        assert_eq!(resp.choices[0].finish_reason, "stop");
        assert_eq!(resp.usage.prompt_tokens, 10);
        assert_eq!(resp.usage.completion_tokens, 5);
        assert_eq!(resp.usage.total_tokens, 15);
    }

    #[tokio::test]
    async fn test_chat_error_status() {
        let server = MockServer::start();
        let engine = OllamaEngine {
            base_url: server.base_url(),
            client: reqwest::Client::new(),
        };

        let _mock = server.mock(|when, then| {
            when.method(POST).path("/api/chat");
            then.status(500).body("internal error");
        });

        let messages = vec![ChatMessage {
            role: "user".to_string(),
            content: "Hi".to_string(),
        }];
        let result = engine.chat("llama3:8b", messages).await;
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("500"));
    }

    #[tokio::test]
    async fn test_chat_stream_success() {
        let server = MockServer::start();
        let engine = OllamaEngine {
            base_url: server.base_url(),
            client: reqwest::Client::new(),
        };

        let ndjson = [
            json!({"message":{"role":"assistant","content":"Hello"},"done":false}).to_string(),
            json!({"message":{"role":"assistant","content":"!"},"done":false}).to_string(),
            json!({"message":{"role":"assistant","content":""},"done":true,"prompt_eval_count":5,"eval_count":2}).to_string(),
        ]
        .join("\n");

        let _mock = server.mock(|when, then| {
            when.method(POST).path("/api/chat");
            then.status(200)
                .header("content-type", "application/x-ndjson")
                .body(ndjson);
        });

        let messages = vec![ChatMessage {
            role: "user".to_string(),
            content: "Hi".to_string(),
        }];
        let mut stream = engine.chat_stream("llama3:8b", messages).await.unwrap();

        let first = stream.next().await.unwrap().unwrap();
        assert_eq!(first.choices[0].delta.content, Some("Hello".to_string()));
        assert!(first.choices[0].finish_reason.is_none());

        let second = stream.next().await.unwrap().unwrap();
        assert_eq!(second.choices[0].delta.content, Some("!".to_string()));
        assert!(second.choices[0].finish_reason.is_none());

        let third = stream.next().await.unwrap().unwrap();
        assert!(third.choices[0].delta.content.is_none());
        assert_eq!(third.choices[0].finish_reason, Some("stop".to_string()));

        assert!(stream.next().await.is_none());
    }

    #[tokio::test]
    async fn test_chat_stream_error_status() {
        let server = MockServer::start();
        let engine = OllamaEngine {
            base_url: server.base_url(),
            client: reqwest::Client::new(),
        };

        let _mock = server.mock(|when, then| {
            when.method(POST).path("/api/chat");
            then.status(500).body("internal error");
        });

        let messages = vec![ChatMessage {
            role: "user".to_string(),
            content: "Hi".to_string(),
        }];
        let result = engine.chat_stream("llama3:8b", messages).await;
        let err = result.err().expect("should be an error");
        assert!(err.to_string().contains("500"));
    }
}
