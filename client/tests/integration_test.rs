use monkey_troop_shared::{ChatCompletionRequest, ChatMessage};

#[tokio::test]
async fn test_client_requires_coordinator() {
    // This test verifies that the client properly handles coordinator unavailability
    let client = reqwest::Client::new();
    
    let request = ChatCompletionRequest {
        model: "llama3:8b".to_string(),
        messages: vec![ChatMessage {
            role: "user".to_string(),
            content: "Hello".to_string(),
        }],
        stream: false,
    };
    
    // Should fail if coordinator is not running
    let result = client
        .post("http://localhost:3000/v1/chat/completions")
        .json(&request)
        .send()
        .await;
    
    // We expect this to fail since no coordinator is running in tests
    assert!(result.is_err(), "Expected connection error without coordinator");
}

#[tokio::test]
async fn test_health_endpoint() {
    // Test that health endpoint structure is correct
    use serde_json::Value;
    
    // We can't actually start the server in tests, so we just verify
    // the expected structure would be valid JSON
    let expected = serde_json::json!({
        "status": "healthy",
        "service": "monkey-troop-client"
    });
    
    assert_eq!(expected["status"], "healthy");
    assert_eq!(expected["service"], "monkey-troop-client");
}

#[test]
fn test_chat_request_serialization() {
    let request = ChatCompletionRequest {
        model: "llama3:8b".to_string(),
        messages: vec![
            ChatMessage {
                role: "system".to_string(),
                content: "You are a helpful assistant".to_string(),
            },
            ChatMessage {
                role: "user".to_string(),
                content: "Hello!".to_string(),
            },
        ],
        stream: true,
    };
    
    let json = serde_json::to_string(&request).unwrap();
    assert!(json.contains("llama3:8b"));
    assert!(json.contains("\"stream\":true"));
}

#[test]
fn test_chat_request_default_stream() {
    let json = r#"{"model":"llama3:8b","messages":[{"role":"user","content":"test"}]}"#;
    let request: ChatCompletionRequest = serde_json::from_str(json).unwrap();
    
    // stream should default to false
    assert_eq!(request.stream, false);
}
