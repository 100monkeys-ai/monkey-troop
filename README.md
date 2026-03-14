# 🐒 Monkey Troop

> **Decentralized AI Compute Grid**

Monkey Troop is a FOSS (MIT Licensed) peer-to-peer network that democratizes access to AI inference. Users donate idle GPU time to run LLM inference for others in exchange for time-based credits, similar to folding@home but for AI.

## 🌟 Vision

Enable anyone to:

- **Donate** idle GPU compute when not in use locally
- **Earn** credits based on actual hardware performance (time-based, normalized)
- **Use** those credits to access high-performance GPUs when needed
- **Trust** the network through cryptographic verification and proof-of-hardware

### Key Features

- **Secure P2P Mesh**: Direct node-to-node connections via Tailscale/Headscale (WireGuard)
- **OpenAI Compatible**: Drop-in replacement for any tool using OpenAI API
- **Fair Economy**: Time-based credits with hardware multipliers (RTX 4090 = 4x, etc.)
- **Proof-of-Hardware**: Cryptographic benchmarking prevents hardware spoofing
- **Trusted Clusters**: Create private networks with friends/teams
- **Public Commons**: Join the global network at `troop.100monkeys.ai`
- **Multi-Engine**: Supports Ollama, LM Studio, vLLM, and more

## 🏗️ Architecture

```markdown
┌─────────────┐         ┌──────────────────┐         ┌─────────────┐
│   Client    │◄───────►│   Coordinator    │◄───────►│   Worker    │
│  (Sidecar)  │ Tickets │ (troop.monkey.ai)│Discovery│   (Agent)   │
│             │         │                  │         │             │
│ localhost:  │         │ - Redis Registry │         │ - Ollama    │
│   9000      │         │ - PostgreSQL     │         │ - Tailscale │
└─────────────┘         │ - JWT Auth       │         │ - GPU       │
      │                 └──────────────────┘         └─────────────┘
      │                                                      ▲
      │                 Direct P2P Connection               │
      └──────────────────────────────────────────────────────┘
              (Encrypted via Tailscale WireGuard)
```

### Components

1. **Coordinator** (Python/FastAPI): Discovery, authentication, proof-of-hardware verification
2. **Worker** (Rust): GPU monitoring, heartbeat broadcasting, JWT verification proxy
3. **Client** (Rust): Local OpenAI-compatible API proxy for seamless integration
4. **Shared** (Rust): Common data structures and types

## 🚀 Quick Start

There are **two installation paths** depending on your role:

### 👥 End Users: Join a Network

Install the worker (to donate GPU) or client (to use GPU) to join an existing network.

```bash
# Install worker/client binaries
curl -fsSL https://raw.githubusercontent.com/100monkeys-ai/monkey-troop/main/bin/install.sh | bash

# Join the public network
export COORDINATOR_URL="https://troop.100monkeys.ai/api"
tailscale up --login-server=https://troop.100monkeys.ai/vpn --authkey=<provided-key>

# Start donating compute
monkey-troop-worker

# OR use the network (in another terminal)
monkey-troop-client
# Point your AI tool to: http://localhost:9000/v1
```

### 🏢 Network Operators: Deploy a Coordinator Hub

Deploy your own coordinator with Headscale VPN for a private network.

```bash
# Clone repository on your VPS
git clone https://github.com/monkeytroop/monkey-troop.git
cd monkey-troop

# Run automated installer (interactive)
./bin/install-coordinator.sh

# OR with command-line flags
./bin/install-coordinator.sh \
  --domain troop.example.com \
  --email admin@example.com \
  --routing-mode path \
  --enable-backups
```

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed documentation.

---

### Self-Host a Private Cluster (Manual)

For advanced users who want full control, see [DEPLOYMENT.md](docs/DEPLOYMENT.md) for manual Headscale setup instructions.

## 🛠️ Development

### Prerequisites

- **Rust** 1.75+ (for worker/client)
- **Python** 3.11+ (for coordinator)
- **Docker** & Docker Compose
- **PostgreSQL** 15+
- **Redis** 7+

### Build from Source

```bash
# Clone the repository
git clone https://github.com/monkeytroop/monkey-troop.git
cd monkey-troop

# Build Rust components
cargo build --release

# Set up Python environment
cd coordinator
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Run Locally

```bash
# Start coordinator stack
docker-compose -f docker/docker-compose.coordinator.yml up -d

# Run worker (requires GPU)
cargo run --bin monkey-troop-worker

# Run client
cargo run --bin monkey-troop-client
```

### Using Streaming

Enable streaming responses for real-time token generation:

```python
import requests

response = requests.post(
    "http://localhost:3000/v1/chat/completions",
    json={
        "model": "llama3:8b",
        "messages": [{"role": "user", "content": "Write a story"}],
        "stream": True
    },
    stream=True
)

for chunk in response.iter_lines():
    if chunk:
        print(chunk.decode('utf-8'))
```

### Multi-Engine Support

Monkey Troop automatically detects and supports multiple inference engines:

- **vLLM** (highest priority - fastest inference)
- **Ollama** (versatile, easy setup)
- **LM Studio** (GUI-based management)

Workers detect all available engines at startup and route requests intelligently based on model availability. vLLM models are prioritized for performance.

**Setup vLLM** (optional):

```bash
# Install vLLM
pip install vllm

# Start vLLM server
vllm serve meta-llama/Llama-3-8B --port 8000

# Or use custom host
export VLLM_HOST=http://localhost:8000
```

**Configure model refresh** (optional):

```bash
# Check for new models every 5 minutes (default: 3 minutes)
export MODEL_REFRESH_INTERVAL=300
```

## 📖 Documentation

- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - Deploy your own Headscale coordinator
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development setup and guidelines
- [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) - Project architecture details
- [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) - Testing instructions

## 🤝 Contributing

Monkey Troop is fully open source (MIT License). Contributions are welcome!

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

## 📜 License

MIT License - Copyright (c) 2026 Monkey Troop Contributors

## 🙏 Acknowledgments
