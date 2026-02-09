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
│           ├── mod.rs              # Engine abstraction & registry
│           ├── ollama.rs           # Ollama driver
│           ├── lmstudio.rs         # LM Studio driver
│           └── vllm.rs             # vLLM driver
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
- **main.rs**: Detects engines, initializes model registry, launches heartbeat and proxy
- **heartbeat.rs**: Broadcasts node status with periodic model refresh (default 3min)
- **proxy.rs**: Axum server that verifies JWT, parses model name, routes to correct engine
- **gpu.rs**: Detects GPU idle state via nvidia-smi
- **engines/**: Multi-engine drivers (Ollama, vLLM, LM Studio) with priority-based routing

### Client (Rust)
- **main.rs**: CLI with `up`, `balance`, `nodes` commands
- **proxy.rs**: Local server on :9000 that mimics OpenAI API, discovers nodes, obtains JWT, connects P2P

### Shared (Rust)
- **models.rs**: Serde types for NodeHeartbeat, ChallengeRequest, JWTClaims, etc.

## Architecture Flow

1. **Worker** detects all available engines (Ollama, vLLM, LM Studio) → builds model registry
2. **Worker** detects idle GPU → broadcasts heartbeat with models from all engines → stored in Redis
3. **Client** receives OpenAI request → asks Coordinator for authorization
4. **Coordinator** finds idle node with requested model → issues signed JWT ticket → returns node IP
5. **Client** connects directly to Worker's Tailscale IP with JWT
6. **Worker** verifies JWT → parses model from request → routes to correct engine → streams response back
7. **No data** passes through Coordinator during inference (pure P2P)
8. **Model registry** refreshes every 3 minutes, heartbeat only sent on changes

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
