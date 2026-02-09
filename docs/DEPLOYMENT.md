# Deploying Monkey Troop

This guide covers deploying your own Monkey Troop coordinator and joining the network.

## 🌍 Joining the Public Network

The easiest way to use Monkey Troop is to join the public network at `troop.100monkeys.ai`.

### As a Worker (Donate GPU)

```bash
# Quick install (coming soon)
curl -sSL https://troop.100monkeys.ai/install.sh | bash

# Manual install
# 1. Download latest release
wget https://github.com/monkeytroop/monkey-troop/releases/latest/monkey-troop-worker

# 2. Install an inference engine (choose one or more):
# Option A: Ollama (recommended for beginners)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3:8b

# Option B: vLLM (fastest, requires Python)
pip install vllm
vllm serve meta-llama/Llama-3-8B --port 8000

# Option C: LM Studio (GUI-based)
# Download from https://lmstudio.ai

# 3. Create .env file
cat > .env << EOF
NODE_ID=$(hostname)
COORDINATOR_URL=https://troop.100monkeys.ai
OLLAMA_HOST=http://localhost:11434
VLLM_HOST=http://localhost:8000
MODEL_REFRESH_INTERVAL=180
EOF

# 4. Start worker (auto-detects all engines)
./monkey-troop-worker
```

### As a Client (Use GPU)

```bash
# Download client
wget https://github.com/monkeytroop/monkey-troop/releases/latest/monkey-troop-client

# Start local proxy
./monkey-troop-client

# Point your AI tools to: http://localhost:9000/v1
```

## 🏠 Self-Hosting a Private Cluster

Deploy your own coordinator for a private cluster.

### Requirements

- **VPS** with at least 2GB RAM, 2 vCPUs (DigitalOcean, Hetzner, etc.)
- **Domain** with DNS access
- **Docker** installed on VPS

### Step 1: Install Headscale

```bash
# SSH into your VPS
ssh user@your-vps.example.com

# Install Headscale
wget https://github.com/juanfont/headscale/releases/latest/download/headscale_*_linux_amd64.deb
sudo dpkg -i headscale_*.deb

# Configure Headscale
sudo nano /etc/headscale/config.yaml
```

Update the configuration:

```yaml
server_url: https://troop.your-domain.com
listen_addr: 0.0.0.0:8080
metrics_listen_addr: 127.0.0.1:9090

# ... rest of config
```

Start Headscale:

```bash
sudo systemctl enable headscale
sudo systemctl start headscale
```

### Step 2: Deploy Coordinator

```bash
# Clone repository
git clone https://github.com/monkeytroop/monkey-troop.git
cd monkey-troop

# Create environment file
cp .env.example .env
nano .env  # Update with secure passwords

# Generate secret key
openssl rand -hex 32  # Copy to .env as SECRET_KEY

# Start coordinator stack
docker-compose -f docker-compose.coordinator.yml up -d

# Check logs
docker-compose -f docker-compose.coordinator.yml logs -f
```

### Step 3: Configure Reverse Proxy (Caddy)

```bash
# Install Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

# Create Caddyfile
sudo nano /etc/caddy/Caddyfile
```

Add configuration:

```
troop.your-domain.com {
    reverse_proxy localhost:8000
}
```

```bash
# Reload Caddy
sudo systemctl reload caddy
```

### Step 4: Connect Workers

On each worker machine:

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Connect to your Headscale
sudo tailscale up --login-server=https://troop.your-domain.com

# Copy the URL shown, then on your VPS:
headscale nodes register --user default --key <NODE_KEY>

# Start worker
./monkey-troop-worker
```

## 🔐 Security Considerations

- **Keep `SECRET_KEY` secure** - Used for JWT signing
- **Use strong database passwords**
- **Enable firewall** - Only expose necessary ports (80, 443, 8080)
- **Regular updates** - Keep Headscale and coordinator updated
- **SSL/TLS required** - Use Caddy or similar for automatic HTTPS

## 📊 Monitoring

```bash
# Check coordinator health
curl https://troop.your-domain.com/health

# View active nodes
curl https://troop.your-domain.com/peers

# Database backup
docker exec troop_db pg_dump -U troop_admin troop_ledger > backup.sql
```

## 🆘 Troubleshooting

### Workers not appearing

- Check Tailscale connection: `tailscale status`
- Verify coordinator URL in worker `.env`
- Check coordinator logs: `docker-compose logs coordinator`

### JWT verification failures

- Ensure clocks are synchronized (NTP)
- Verify `SECRET_KEY` matches on coordinator

### Database connection errors

- Check PostgreSQL is running: `docker ps`
- Verify credentials in `.env`
- Check network connectivity between containers

## 🔄 Updates

```bash
# Update coordinator
cd monkey-troop
git pull
docker-compose -f docker-compose.coordinator.yml down
docker-compose -f docker-compose.coordinator.yml up -d --build

# Update worker
wget https://github.com/monkeytroop/monkey-troop/releases/latest/monkey-troop-worker
sudo systemctl restart monkey-troop-worker
```

---

For more help, join our community or open an issue on GitHub.
