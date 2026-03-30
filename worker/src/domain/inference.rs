use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceRequest {
    pub model_id: String,
    pub messages: Vec<ChatMessage>,
    pub stream: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceChoice {
    pub index: usize,
    pub message: ChatMessage,
    pub finish_reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenUsage {
    pub prompt_tokens: u32,
    pub completion_tokens: u32,
    pub total_tokens: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceResponse {
    pub id: String,
    pub object: String,
    pub created: u64,
    pub model: String,
    pub choices: Vec<InferenceChoice>,
    pub usage: TokenUsage,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StreamingChunk {
    pub id: String,
    pub object: String,
    pub created: u64,
    pub model: String,
    pub choices: Vec<StreamingChoice>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StreamingChoice {
    pub index: usize,
    pub delta: ChatMessageDelta,
    pub finish_reason: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessageDelta {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub content: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json;

    #[test]
    fn test_inference_request_serialization() {
        let request = InferenceRequest {
            model_id: "test-model".to_string(),
            messages: vec![ChatMessage {
                role: "user".to_string(),
                content: "hello".to_string(),
            }],
            stream: false,
        };

        let serialized = serde_json::to_string(&request).unwrap();
        let deserialized: InferenceRequest = serde_json::from_str(&serialized).unwrap();

        assert_eq!(deserialized.model_id, "test-model");
        assert_eq!(deserialized.messages.len(), 1);
        assert_eq!(deserialized.messages[0].content, "hello");
        assert!(!deserialized.stream);
    }

    #[test]
    fn test_inference_response_serialization() {
        let response = InferenceResponse {
            id: "test-id".to_string(),
            object: "chat.completion".to_string(),
            created: 123456789,
            model: "test-model".to_string(),
            choices: vec![InferenceChoice {
                index: 0,
                message: ChatMessage {
                    role: "assistant".to_string(),
                    content: "response content".to_string(),
                },
                finish_reason: "stop".to_string(),
            }],
            usage: TokenUsage {
                prompt_tokens: 10,
                completion_tokens: 20,
                total_tokens: 30,
            },
        };

        let serialized = serde_json::to_string(&response).unwrap();
        let deserialized: InferenceResponse = serde_json::from_str(&serialized).unwrap();

        assert_eq!(deserialized.id, "test-id");
        assert_eq!(deserialized.choices[0].message.content, "response content");
    }

    #[test]
    fn test_streaming_chunk_serialization() {
        let chunk = StreamingChunk {
            id: "chatcmpl-123".to_string(),
            object: "chat.completion.chunk".to_string(),
            created: 1677652288,
            model: "llama3:8b".to_string(),
            choices: vec![StreamingChoice {
                index: 0,
                delta: ChatMessageDelta {
                    role: None,
                    content: Some("Hello".to_string()),
                },
                finish_reason: None,
            }],
        };

        let serialized = serde_json::to_string(&chunk).unwrap();
        let deserialized: StreamingChunk = serde_json::from_str(&serialized).unwrap();

        assert_eq!(deserialized.id, "chatcmpl-123");
        assert_eq!(deserialized.object, "chat.completion.chunk");
        assert_eq!(
            deserialized.choices[0].delta.content,
            Some("Hello".to_string())
        );
        assert!(deserialized.choices[0].delta.role.is_none());
        assert!(deserialized.choices[0].finish_reason.is_none());
    }

    #[test]
    fn test_streaming_chunk_skip_serializing_none() {
        let delta = ChatMessageDelta {
            role: None,
            content: None,
        };

        let serialized = serde_json::to_string(&delta).unwrap();
        assert!(!serialized.contains("role"));
        assert!(!serialized.contains("content"));
    }

    #[test]
    fn test_streaming_choice_with_finish_reason() {
        let choice = StreamingChoice {
            index: 0,
            delta: ChatMessageDelta {
                role: Some("assistant".to_string()),
                content: None,
            },
            finish_reason: Some("stop".to_string()),
        };

        let serialized = serde_json::to_string(&choice).unwrap();
        let deserialized: StreamingChoice = serde_json::from_str(&serialized).unwrap();

        assert_eq!(deserialized.delta.role, Some("assistant".to_string()));
        assert!(deserialized.delta.content.is_none());
        assert_eq!(deserialized.finish_reason, Some("stop".to_string()));
    }
}
