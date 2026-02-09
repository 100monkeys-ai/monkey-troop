# Monkey Troop - Project Structure

```
monkey-troop/
├── Cargo.toml                      # Rust workspace root
├── LICENSE                         # MIT License
├── README.md                       # Project overview
├── CONTRIBUTING.md                 # Contribution guidelines
├── DEPLOYMENT.md                   # Deployment instructions
├── .gitignore                      # Git ignore rules
├── .env.example                    # Environment template
├── start.sh                        # Quick start script
├── install.sh                      # Installation script
│
├── coordinator/                    # Python/FastAPI service
│   ├── __init__.py
│   ├── main.py                     # API endpoints
│   ├── database.py                 # SQLAlchemy models
│   ├── auth.py                     # JWT handling
│   ├── benchmark.py                # PoH benchmark script
│   ├── pyproject.toml              # Python package config
│   ├── requirements.txt            # Dependencies
│   └── Dockerfile                  # Container image
│
├── worker/                         # Rust worker agent
│   ├── Cargo.toml
│   ├── Dockerfile
│   └── src/
│       ├── main.rs                 # Entry point
│       ├── config.rs               # Configuration
│       ├── gpu.rs                  # GPU detection
│       ├── heartbeat.rs            # Coordinator communication
│       ├── proxy.rs                # JWT verification proxy
│       └── engines/
│           ├── mod.rs              # Engine abstraction
│           ├── ollama.rs           # Ollama driver
│           └── lmstudio.rs         # LM Studio driver
│
├── client/                         # Rust client sidecar
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs                 # CLI interface
│       ├── config.rs               # Configuration
│       └── proxy.rs                # OpenAI-compatible proxy
│
├── shared/                         # Shared Rust types
│   ├── Cargo.toml
│   └── src/
│       ├── lib.rs
│       └── models.rs               # Common data structures
│
├── docker-compose.coordinator.yml  # Coordinator stack
└── docker-compose.worker.yml       # Worker stack
```

## Key Files

### Coordinator (Python)
- **main.py**: FastAPI endpoints for heartbeat, discovery, PoH, authorization
- **database.py**: Users, Nodes, Transactions tables with credit ledger
- **auth.py**: JWT ticket generation and verification
- **benchmark.py**: PyTorch matrix multiplication for hardware verification

### Worker (Rust)
- **main.rs**: Launches heartbeat loop and JWT proxy simultaneously
- **heartbeat.rs**: Broadcasts node status every 10s to coordinator
- **proxy.rs**: Axum server that verifies JWT tickets before forwarding to Ollama
- **gpu.rs**: Detects GPU idle state via nvidia-smi
- **engines/**: Adapters for Ollama, LM Studio, etc.

### Client (Rust)
- **main.rs**: CLI with `up`, `balance`, `nodes` commands
- **proxy.rs**: Local server on :9000 that mimics OpenAI API, discovers nodes, obtains JWT, connects P2P

### Shared (Rust)
- **models.rs**: Serde types for NodeHeartbeat, ChallengeRequest, JWTClaims, etc.

## Architecture Flow

1. **Worker** detects idle GPU → broadcasts heartbeat to Coordinator → stored in Redis
2. **Client** receives OpenAI request → asks Coordinator for authorization
3. **Coordinator** finds idle node → issues signed JWT ticket → returns node IP
4. **Client** connects directly to Worker's Tailscale IP with JWT
5. **Worker** verifies JWT → forwards to local Ollama → streams response back
6. **No data** passes through Coordinator during inference (pure P2P)

## Development Commands

```bash
# Build everything
cargo build --workspace

# Run coordinator locally
cd coordinator && uvicorn main:app --reload

# Run worker
cargo run --bin monkey-troop-worker

# Run client
cargo run --bin monkey-troop-client up

# Run tests
cargo test --workspace
cd coordinator && pytest

# Format code
cargo fmt --all
cd coordinator && black .

# Lint
cargo clippy --all-targets
cd coordinator && ruff check .
```

## Docker Deployment

```bash
# Start coordinator
docker-compose -f docker-compose.coordinator.yml up -d

# Start worker
docker-compose -f docker-compose.worker.yml up -d

# View logs
docker-compose logs -f coordinator
```
