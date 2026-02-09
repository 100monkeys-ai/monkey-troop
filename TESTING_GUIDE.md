# Quick Start: Testing Phase 2 Features

## Prerequisites
```bash
# Install Python dependencies
cd coordinator
pip3 install -r requirements.txt

# Verify Rust compiles
cd ..
cargo check --workspace
```

## 1. Credit Accounting

### Start Coordinator
```bash
cd coordinator
export DATABASE_URL="postgresql://troop:password@localhost/troop_coordinator"
export REDIS_HOST="localhost"
export RECEIPT_SECRET="test-secret-12345"
python3 -m uvicorn main:app --reload
```

### Test Starter Credits
```bash
# New user gets 1 hour (3600s) automatically
curl http://localhost:8000/users/alice_public_key/balance

# Response: {"public_key": "alice_public_key", "balance_seconds": 3600, "balance_hours": 1.0}
```

### Test Authorization with Balance Check
```bash
# Register a fake worker
redis-cli SET "node:test_worker" '{"node_id":"test_worker","tailscale_ip":"100.64.0.1","status":"IDLE","models":["llama2:7b"],"hardware":{"gpu":"Test","vram_free":8192},"engine":{"type":"ollama","version":"0.1","port":11434}}' EX 60

# Request authorization (reserves 300s)
curl -X POST http://localhost:8000/authorize \
  -H "Content-Type: application/json" \
  -d '{"model": "llama2:7b", "requester": "alice_public_key"}'

# Check balance again (should be 3300s)
curl http://localhost:8000/users/alice_public_key/balance
```

### Test Insufficient Credits
```bash
# Create user with low balance (need to manually set in DB or deplete)
curl -X POST http://localhost:8000/authorize \
  -H "Content-Type: application/json" \
  -d '{"model": "llama2:7b", "requester": "poor_user"}'

# After depleting, should get 402 Payment Required
```

### Test Job Completion
```bash
# Generate HMAC signature (in Python)
python3 << 'EOF'
import hmac, hashlib
job_id = "job_123"
node_id = "test_worker"
duration = 250
secret = "test-secret-12345"
message = f"{job_id}:{node_id}:{duration}".encode()
sig = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
print(sig)
EOF

# Submit job completion with signature
curl -X POST http://localhost:8000/transactions/submit \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "job_123",
    "requester_public_key": "alice_public_key",
    "worker_node_id": "test_worker",
    "duration_seconds": 250,
    "signature": "<paste_signature_from_above>"
  }'
```

## 2. Rate Limiting

### Test Discovery Rate Limit (100/hour)
```bash
# Spam requests
for i in {1..110}; do
  curl -s http://localhost:8000/v1/models | jq .error
  sleep 0.1
done

# Should eventually see: {"error": "Rate limit exceeded", "limit": 100, "window": "1 hour"}
```

### Check Audit Logs
```bash
tail -f coordinator/logs/audit.log | jq .
```

## 3. RSA JWT Verification

### Get Public Key
```bash
curl http://localhost:8000/public-key
# Should return PEM-formatted RSA public key
```

### Test Worker Verification
```bash
cd worker
cargo run

# In logs, should see:
# ✓ Public key loaded from coordinator
# 🔐 Starting JWT verification proxy on 0.0.0.0:8080
```

### Test Invalid Token Rejection
```bash
# Try to call worker with fake token
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer fake.invalid.token" \
  -H "Content-Type: application/json" \
  -d '{"model": "llama2:7b", "messages": [{"role": "user", "content": "Hi"}]}'

# Should get 401 Unauthorized
```

## 4. Proof-of-Hardware Benchmark

### Run Benchmark Manually
```bash
cd worker
python3 benchmark.py test_seed_123 4096
# Output: {"proof_hash": "abc...", "duration": 15.2, "device": "NVIDIA RTX 3090"}
```

### Test Worker Startup Benchmark
```bash
export RUN_INITIAL_BENCHMARK=true
cargo run

# Logs should show:
# Running initial hardware benchmark...
# ✓ Benchmark: 15.234s on NVIDIA RTX 3090
```

### Test CPU Fallback
```bash
# Rename torch to simulate missing PyTorch
mv ~/.local/lib/python3.9/site-packages/torch ~/.local/lib/python3.9/site-packages/torch.bak

python3 benchmark.py test_seed_456 512
# Output: {"proof_hash": "...", "duration": 45.6, "device": "CPU (fallback)"}

# Restore
mv ~/.local/lib/python3.9/site-packages/torch.bak ~/.local/lib/python3.9/site-packages/torch
```

## 5. Circuit Breaker

### Test Heartbeat Circuit Breaker
```bash
# Start worker
cd worker
cargo run

# Stop coordinator
# Worker logs should show:
# Failed to send heartbeat: ...
# Failed to send heartbeat: ...
# ... (5 failures)
# ⚠ Circuit breaker OPEN - skipping heartbeat attempt

# Wait 60 seconds
# Circuit breaker HALF-OPEN - attempting recovery

# Restart coordinator
# ✓ Heartbeat sent successfully
# Circuit breaker CLOSED
```

## 6. Error Handling & Retry

### Test Client Retry Logic
```bash
cd client
cargo run -- up

# Temporarily stop coordinator
# Client logs should show:
# get_authorization failed (attempt 1): Network error: ...
# Retrying in 1s...
# get_authorization failed (attempt 2): Network error: ...
# Retrying in 2s...

# Restart coordinator within retry window
# ✓ Authorization succeeded on retry attempt 3
```

## 7. Integration Tests

### Run Python Tests
```bash
cd coordinator

# Unit tests (no services needed)
pytest tests/test_transactions.py -v

# Audit log tests
pytest tests/test_audit.py -v

# Integration tests (requires coordinator + Redis + PostgreSQL running)
docker-compose up -d
pytest tests/test_integration.py -v
```

## 8. Transaction History

### View User Transactions
```bash
curl http://localhost:8000/users/alice_public_key/transactions?limit=10 | jq .

# Response:
# {
#   "transactions": [
#     {
#       "id": 1,
#       "from_user": null,
#       "to_user": "alice_public_key",
#       "credits": 3600,
#       "duration": 0,
#       "job_id": "starter_grant",
#       "timestamp": "2026-02-08T12:00:00",
#       "type": "starter_grant"
#     },
#     {
#       "id": 2,
#       "from_user": "alice_public_key",
#       "to_user": "bob_public_key",
#       "credits": 500,
#       "duration": 250,
#       "job_id": "job_123",
#       "timestamp": "2026-02-08T12:05:00",
#       "type": "job"
#     }
#   ]
# }
```

## Troubleshooting

### Database Connection Errors
```bash
# Check PostgreSQL is running
docker-compose ps

# Check connection
psql $DATABASE_URL -c "SELECT 1;"
```

### Redis Connection Errors
```bash
# Check Redis is running
redis-cli ping
# Should return: PONG
```

### RSA Key Not Found
```bash
# Check keys directory exists
ls -la coordinator/keys/
# Should see: troop_private_key.pem, troop_public_key.pem

# Regenerate if missing
cd coordinator
python3 -c "from crypto import ensure_keys_exist; ensure_keys_exist()"
```

### Worker Can't Verify JWT
```bash
# Check coordinator is accessible
curl http://coordinator_url:8000/public-key

# Check worker logs for public key fetch errors
# If coordinator URL wrong, update COORDINATOR_URL env var
```

## Monitoring

### Watch Audit Logs in Real-Time
```bash
tail -f coordinator/logs/audit.log | jq 'select(.message.event == "authorization")'
```

### Monitor Redis Keys
```bash
redis-cli KEYS "*"
redis-cli GET "node:test_worker"
redis-cli GET "ratelimit:discovery:127.0.0.1"
```

### Check Database State
```bash
psql $DATABASE_URL << 'EOF'
SELECT public_key, balance_seconds, created_at FROM users LIMIT 5;
SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 10;
SELECT node_id, multiplier, total_jobs_completed FROM nodes;
EOF
```
