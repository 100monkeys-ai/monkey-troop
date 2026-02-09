use serde::{Deserialize, Serialize};

/// Information about the inference engine running on a node
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EngineInfo {
    #[serde(rename = "type")]
    pub engine_type: String, // "ollama", "lmstudio", "vllm"
    pub version: String,
    pub port: u16,
}

/// Hardware specifications of a node
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareInfo {
    pub gpu: String,
    pub vram_free: u64, // MB
}

/// Node status broadcast to coordinator
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeHeartbeat {
    pub node_id: String,
    pub tailscale_ip: String,
    pub status: NodeStatus,
    pub models: Vec<String>,
    pub hardware: HardwareInfo,
    pub engines: Vec<EngineInfo>,
}

/// Current operational status of a node
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum NodeStatus {
    Idle,
    Busy,
    Offline,
}

/// Challenge issued by coordinator for proof-of-hardware
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChallengeRequest {
    pub node_id: String,
}

/// Response containing benchmark challenge parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChallengeResponse {
    pub challenge_token: String,
    pub seed: String,
    pub matrix_size: u32,
}

/// Proof-of-work submission from node
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerifyRequest {
    pub node_id: String,
    pub challenge_token: String,
    pub proof_hash: String,
    pub duration: f64, // seconds
    pub device_name: String,
}

/// Verification result with assigned multiplier
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerifyResponse {
    pub status: String,
    pub assigned_multiplier: f64,
    pub tier: String,
}

/// JWT claims for authorization tickets
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JWTClaims {
    pub sub: String,         // user_id (requester)
    pub target_node: String, // node_id receiving the work
    pub aud: String,         // "swarm-worker"
    pub exp: i64,            // expiration timestamp
    pub project: String,     // tier: "free-tier", "premium", etc.
}

/// Request for authorization ticket
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthorizeRequest {
    pub model: String,
    pub requester: String, // Tailscale IP or user ID
}

/// Authorization ticket response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthorizeResponse {
    pub target_ip: String,
    pub token: String, // Signed JWT
}

/// OpenAI-compatible chat message
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

/// OpenAI-compatible chat completion request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatCompletionRequest {
    pub model: String,
    pub messages: Vec<ChatMessage>,
    #[serde(default)]
    pub stream: bool,
}

/// List of available peers
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PeersResponse {
    pub count: usize,
    pub nodes: Vec<NodeHeartbeat>,
}

/// OpenAI-compatible model list
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelInfo {
    pub id: String,
    pub object: String,
    pub owned_by: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelsResponse {
    pub object: String,
    pub data: Vec<ModelInfo>,
}
