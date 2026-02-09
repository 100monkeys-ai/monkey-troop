# Coordinator Tests

Run all tests:
```bash
cd coordinator
pytest tests/ -v
```

Run specific test file:
```bash
pytest tests/test_transactions.py -v
```

Run integration tests (requires coordinator running):
```bash
# Terminal 1: Start services
docker-compose up

# Terminal 2: Run tests
pytest tests/test_integration.py -v
```

## Test Coverage

- `test_transactions.py` - Credit accounting, balance checks, job completion
- `test_integration.py` - End-to-end API workflows, rate limiting, JWT structure
- `test_audit.py` - Audit logging functionality

## Adding New Tests

1. Create test file in `tests/test_*.py`
2. Use pytest fixtures for database/client setup
3. Follow existing patterns for async tests
4. Run tests before committing code
