#!/bin/bash

###############################################################################
# Headscale Installation Script
#
# Downloads, configures, and installs Headscale VPN server
# - Downloads latest Headscale binary from GitHub
# - Generates configuration file
# - Installs systemd service
# - Creates initial pre-auth key
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DOMAIN=""
ROUTING_MODE="path"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --routing-mode)
            ROUTING_MODE="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

if [[ -z "$DOMAIN" ]]; then
    log_error "Domain is required"
fi

# Determine server URL based on routing mode
if [[ "$ROUTING_MODE" == "subdomain" ]]; then
    SERVER_URL="https://vpn.$DOMAIN"
else
    SERVER_URL="https://$DOMAIN/vpn"
fi

log_info "Installing Headscale VPN server..."
log_info "Server URL: $SERVER_URL"

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        HEADSCALE_ARCH="amd64"
        ;;
    aarch64|arm64)
        HEADSCALE_ARCH="arm64"
        ;;
    armv7l)
        HEADSCALE_ARCH="arm"
        ;;
    *)
        log_error "Unsupported architecture: $ARCH"
        ;;
esac

log_info "Detected architecture: $HEADSCALE_ARCH"

# Get latest Headscale version
log_info "Fetching latest Headscale version..."
HEADSCALE_VERSION=$(curl -s https://api.github.com/repos/juanfont/headscale/releases/latest | grep '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')

if [[ -z "$HEADSCALE_VERSION" ]]; then
    log_error "Failed to fetch Headscale version"
fi

log_info "Latest version: v$HEADSCALE_VERSION"

# Download Headscale
HEADSCALE_URL="https://github.com/juanfont/headscale/releases/download/v${HEADSCALE_VERSION}/headscale_${HEADSCALE_VERSION}_linux_${HEADSCALE_ARCH}"
TEMP_DIR=$(mktemp -d)

log_info "Downloading Headscale..."
curl -L -o "$TEMP_DIR/headscale" "$HEADSCALE_URL" || log_error "Failed to download Headscale"

# Install binary
log_info "Installing Headscale binary..."
sudo install -o root -g root -m 755 "$TEMP_DIR/headscale" /usr/local/bin/headscale
rm -rf "$TEMP_DIR"

log_success "Headscale binary installed"

# Create Headscale directories
log_info "Creating Headscale directories..."
sudo mkdir -p /etc/headscale
sudo mkdir -p /var/lib/headscale
sudo mkdir -p /var/run/headscale

# Generate configuration
log_info "Generating Headscale configuration..."

# Use template if exists, otherwise create from scratch
if [[ -f "$SCRIPT_DIR/config/headscale.yaml.template" ]]; then
    sudo cp "$SCRIPT_DIR/config/headscale.yaml.template" /etc/headscale/config.yaml
    sudo sed -i "s|SERVER_URL_PLACEHOLDER|$SERVER_URL|g" /etc/headscale/config.yaml
else
    # Generate basic config inline
    sudo tee /etc/headscale/config.yaml > /dev/null <<EOF
server_url: $SERVER_URL
listen_addr: 127.0.0.1:8080
metrics_listen_addr: 127.0.0.1:9090

grpc_listen_addr: 127.0.0.1:50443
grpc_allow_insecure: false

private_key_path: /var/lib/headscale/private.key
noise:
  private_key_path: /var/lib/headscale/noise_private.key

ip_prefixes:
  - 100.64.0.0/10

derp:
  server:
    enabled: false
  urls:
    - https://controlplane.tailscale.com/derpmap/default
  auto_update_enabled: true
  update_frequency: 24h

disable_check_updates: false
ephemeral_node_inactivity_timeout: 30m

database:
  type: sqlite3
  sqlite:
    path: /var/lib/headscale/db.sqlite

log:
  level: info
  format: text

dns_config:
  override_local_dns: true
  nameservers:
    - 1.1.1.1
    - 8.8.8.8
  domains: []
  magic_dns: true
  base_domain: $DOMAIN

unix_socket: /var/run/headscale/headscale.sock
unix_socket_permission: "0770"

logtail:
  enabled: false

randomize_client_port: false
EOF
fi

log_success "Configuration generated"

# Install systemd service
log_info "Installing systemd service..."

if [[ -f "$SCRIPT_DIR/systemd/headscale.service" ]]; then
    sudo cp "$SCRIPT_DIR/systemd/headscale.service" /etc/systemd/system/headscale.service
else
    sudo tee /etc/systemd/system/headscale.service > /dev/null <<EOF
[Unit]
Description=Headscale VPN Control Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
ExecStart=/usr/local/bin/headscale serve
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/headscale /var/run/headscale
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
EOF
fi

# Reload systemd and start service
log_info "Starting Headscale service..."
sudo systemctl daemon-reload
sudo systemctl enable headscale
sudo systemctl start headscale

# Wait for service to start
sleep 3

# Check if service is running
if systemctl is-active --quiet headscale; then
    log_success "Headscale service is running"
else
    log_error "Headscale service failed to start. Check: journalctl -u headscale -n 50"
fi

# Create default namespace (if doesn't exist)
log_info "Creating default namespace..."
sudo headscale namespaces create default 2>/dev/null || log_info "Namespace 'default' already exists"

# Generate pre-auth key
log_info "Generating pre-authentication key..."
PREAUTH_KEY=$(sudo headscale preauthkeys create --namespace default --expiration 90d --reusable | grep -oP '(?<=key: )[a-f0-9]+' || sudo headscale preauthkeys create --namespace default --expiration 90d --reusable | awk '{print $NF}')

if [[ -z "$PREAUTH_KEY" ]]; then
    # Try alternative parsing
    PREAUTH_KEY=$(sudo headscale preauthkeys create --namespace default --expiration 90d --reusable 2>&1 | tail -1 | awk '{print $NF}')
fi

if [[ -z "$PREAUTH_KEY" ]]; then
    log_error "Failed to generate pre-auth key"
fi

log_success "Headscale installation complete"
log_info "Pre-auth key generated (valid for 90 days)"

# Output the pre-auth key to stdout (captured by parent script)
echo "$PREAUTH_KEY"
