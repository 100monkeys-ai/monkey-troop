# Contributing to Monkey Troop

Thank you for your interest in contributing to Monkey Troop! This document provides guidelines for contributing to the project.

## 🏗️ Development Setup

### Prerequisites

- **Rust** 1.75 or later
- **Python** 3.11 or later
- **Docker** and Docker Compose
- **Git**

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/monkeytroop/monkey-troop.git
cd monkey-troop

# Build Rust workspace
cargo build

# Set up Python environment
cd coordinator
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e ".[dev]"  # Install dev dependencies
cd ..
```

### Running Tests

```bash
# Rust tests
cargo test --workspace

# Python tests (requires PostgreSQL and Redis)
cd coordinator
# Set up test environment variables
export DATABASE_URL=postgresql://postgres:testpass@localhost:5432/test_troop
export REDIS_URL=redis://localhost:6379
pytest -v

# Integration tests with Docker
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

### Database Migrations

When adding new database features, create migrations:

```bash
cd coordinator

# Create a new migration
alembic revision --autogenerate -m "add_my_feature"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Check current version
alembic current
```

**Migration Best Practices:**
- Always test migrations in a dev environment first
- Include both `upgrade()` and `downgrade()` functions
- Use descriptive migration messages
- Add indexes for frequently queried columns
- Never modify existing migrations once merged to main

### Code Style

**Rust:**
- Follow standard Rust formatting: `cargo fmt`
- Run clippy: `cargo clippy --all-targets`
- Fix warnings before committing

**Python:**
- Format with Black: `black .`
- Sort imports with isort: `isort .`
- Lint with flake8: `flake8 --max-line-length=120 .`
- Type hints are encouraged (checked with mypy)

### Streaming Responses

The system supports streaming for chat completions:

```python
# Client request with streaming
{
  "model": "llama3:8b",
  "messages": [...],
  "stream": true  # Enable Server-Sent Events
}
```

**Implementation Notes:**
- Client: Passes through SSE stream from worker
- Worker: Passes through SSE stream from Ollama
- No buffering in the pipeline for streaming responses
- Content-Type: `text/event-stream`

## 🔄 Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests and linters
5. Commit with clear messages
6. Push to your fork
7. Open a Pull Request

## 📝 Commit Messages

Use clear, descriptive commit messages:

```
feat: add proof-of-hardware benchmark
fix: resolve JWT expiration bug
docs: update deployment guide
refactor: simplify heartbeat logic
```

## 🐛 Reporting Issues

When reporting issues, include:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- System information (OS, Rust/Python version, GPU model)
- Relevant logs

## 💡 Feature Requests

We welcome feature requests! Please:
- Check existing issues first
- Describe the use case
- Explain how it aligns with the project goals

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.
