# 🐒 Monkey Troop

**Decentralized AI Compute Grid**

Monkey Troop is a FOSS (MIT Licensed) peer-to-peer network that democratizes access to AI inference. Users donate idle GPU time to run LLM inference for others in exchange for time-based credits, similar to folding@home but for AI.

## 🌟 Vision

Enable anyone to:
- **Donate** idle GPU compute when not in use locally
- **Earn** credits based on actual hardware performance (time-based, normalized)
- **Use** those credits to access high-performance GPUs when needed
- **Trust** the network through cryptographic verification and proof-of-hardware

### Key Features

- **🔒 Secure P2P Mesh**: Direct node-to-node connections via Tailscale/Headscale (WireGuard)
- **🎯 OpenAI Compatible**: Drop-in replacement for any tool using OpenAI API
- **⚖️ Fair Economy**: Time-based credits with hardware multipliers (RTX 4090 = 4x, etc.)
- **🔐 Proof-of-Hardware**: Cryptographic benchmarking prevents hardware spoofing
- **🤝 Trusted Clusters**: Create private networks with friends/teams
- **🌍 Public Commons**: Join the global network at `troop.100monkeys.ai`
- **🔧 Multi-Engine**: Supports Ollama, LM Studio, vLLM, and more

## 🏗️ Architecture

```
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

### Join the Public Network

```bash
# Install the worker
curl -sSL https://troop.100monkeys.ai/install.sh | bash

# Start donating compute
monkey-troop-worker up

# Use the network (in another terminal)
monkey-troop-client up

# Point your AI tool to: http://localhost:9000/v1
```

### Self-Host a Private Cluster

See [DEPLOYMENT.md](DEPLOYMENT.md) for Headscale setup instructions.

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
docker-compose -f docker-compose.coordinator.yml up -d

# Run worker (requires GPU)
cargo run --bin monkey-troop-worker

# Run client
cargo run --bin monkey-troop-client
```

## 📖 Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Deploy your own Headscale coordinator
- [CONTRIBUTING.md](CONTRIBUTING.md) - Development setup and guidelines
- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed system design (coming soon)

## 🤝 Contributing

Monkey Troop is fully open source (MIT License). Contributions are welcome!

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

## 📜 License

MIT License - Copyright (c) 2026 Monkey Troop Contributors

## 🙏 Acknowledgments

Inspired by:
- [Petals](https://github.com/bigscience-workshop/petals) - Distributed inference concepts
- [Folding@home](https://foldingathome.org/) - Distributed computing for good
- [Ollama](https://ollama.ai/) - Local LLM runtime
- [Tailscale](https://tailscale.com/) - Zero-config VPN mesh networking

---

**🚨 Status**: Early Development (Pre-Alpha)

This project is under active development. The MVP is not yet functional. Join us in building the future of decentralized AI!
