#!/bin/bash

###############################################################################
# Coordinator Stack Installation Script
#
# Installs and configures the Monkey Troop coordinator stack:
# - Docker and Docker Compose
# - PostgreSQL database
# - Redis cache
# - Coordinator API service
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
DB_PASSWORD=""
ADMIN_PASSWORD=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
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
        --db-password)
            DB_PASSWORD="$2"
            shift 2
            ;;
        --admin-password)
            ADMIN_PASSWORD="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

if [[ -z "$DOMAIN" || -z "$DB_PASSWORD" || -z "$ADMIN_PASSWORD" ]]; then
    log_error "Domain, DB password, and admin password are required"
fi

# Determine coordinator URL based on routing mode
if [[ "$ROUTING_MODE" == "subdomain" ]]; then
    COORDINATOR_URL="https://api.$DOMAIN"
else
    COORDINATOR_URL="https://$DOMAIN/api"
fi

log_info "Installing Coordinator stack..."
log_info "Coordinator URL: $COORDINATOR_URL"

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    log_info "Installing Docker..."
    
    if [[ -f /etc/debian_version ]]; then
        # Debian/Ubuntu
        sudo apt-get update
        sudo apt-get install -y ca-certificates curl gnupg
        sudo install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
        
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
          $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
          sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        sudo apt-get update
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    elif [[ -f /etc/redhat-release ]]; then
        # RHEL/CentOS/Fedora
        sudo yum install -y yum-utils
        sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        sudo systemctl start docker
        sudo systemctl enable docker
    else
        log_error "Unsupported OS for automatic Docker installation. Please install Docker manually."
    fi
    
    log_success "Docker installed"
else
    log_info "Docker already installed"
fi

# Verify Docker Compose
if ! docker compose version &>/dev/null; then
    log_error "Docker Compose plugin not found. Please install Docker Compose."
fi

log_success "Docker Compose available"

# Create coordinator directory
COORDINATOR_DIR="/opt/monkey-troop"
log_info "Creating coordinator directory: $COORDINATOR_DIR"
sudo mkdir -p "$COORDINATOR_DIR"
sudo chown $USER:$USER "$COORDINATOR_DIR"

# Copy coordinator files
log_info "Copying coordinator files..."
cp -r "$SCRIPT_DIR/coordinator" "$COORDINATOR_DIR/"
cp "$SCRIPT_DIR/docker-compose.coordinator.yml" "$COORDINATOR_DIR/docker-compose.yml"

# Generate SECRET_KEY
SECRET_KEY=$(openssl rand -hex 32)

# Generate .env file
log_info "Generating environment configuration..."
cat > "$COORDINATOR_DIR/.env" <<EOF
# Database Configuration
DATABASE_URL=postgresql://troop_admin:${DB_PASSWORD}@postgres:5432/troop_ledger
DB_USER=troop_admin
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=troop_ledger

# Redis Configuration
REDIS_URL=redis://redis:6379
REDIS_HOST=redis
REDIS_PORT=6379

# Coordinator Configuration
SECRET_KEY=${SECRET_KEY}
COORDINATOR_URL=${COORDINATOR_URL}
JWT_EXPIRATION_SECONDS=300
STARTER_CREDITS=1000.0
ADMIN_PASSWORD=${ADMIN_PASSWORD}

# CORS Configuration
ALLOWED_ORIGINS=https://${DOMAIN},http://localhost:3000

# Logging
LOG_LEVEL=INFO

# Optional: Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
EOF

log_success "Environment configuration created"

# Create data directories
log_info "Creating data directories..."
mkdir -p "$COORDINATOR_DIR/data/postgres"
mkdir -p "$COORDINATOR_DIR/data/redis"
mkdir -p "$COORDINATOR_DIR/coordinator/logs"
mkdir -p "$COORDINATOR_DIR/coordinator/keys"

# Update docker-compose.yml to use local paths
log_info "Configuring Docker Compose..."
sed -i.bak "s|./coordinator|$COORDINATOR_DIR/coordinator|g" "$COORDINATOR_DIR/docker-compose.yml"
rm -f "$COORDINATOR_DIR/docker-compose.yml.bak"

# Install systemd service
log_info "Installing systemd service..."

if [[ -f "$SCRIPT_DIR/systemd/coordinator-stack.service" ]]; then
    sudo cp "$SCRIPT_DIR/systemd/coordinator-stack.service" /etc/systemd/system/coordinator-stack.service
    sudo sed -i "s|WORKING_DIRECTORY_PLACEHOLDER|$COORDINATOR_DIR|g" /etc/systemd/system/coordinator-stack.service
else
    sudo tee /etc/systemd/system/coordinator-stack.service > /dev/null <<EOF
[Unit]
Description=Monkey Troop Coordinator Stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$COORDINATOR_DIR
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
fi

# Start coordinator stack
log_info "Starting coordinator stack..."
cd "$COORDINATOR_DIR"
sudo systemctl daemon-reload
sudo systemctl enable coordinator-stack
sudo systemctl start coordinator-stack

# Wait for services to be healthy
log_info "Waiting for services to start..."
sleep 10

# Check if containers are running
if docker compose ps | grep -q "Up"; then
    log_success "Coordinator stack is running"
else
    log_error "Coordinator stack failed to start. Check: docker compose logs"
fi

# Wait for coordinator API to be ready
log_info "Waiting for coordinator API to be ready..."
MAX_ATTEMPTS=30
ATTEMPT=0

while [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; do
    if curl -f http://localhost:8000/health &>/dev/null || curl -f http://localhost:8000/ &>/dev/null; then
        log_success "Coordinator API is responding"
        break
    fi
    
    ATTEMPT=$((ATTEMPT + 1))
    if [[ $ATTEMPT -eq $MAX_ATTEMPTS ]]; then
        log_error "Coordinator API failed to respond. Check: docker compose logs coordinator"
    fi
    
    sleep 2
done

log_success "Coordinator stack installation complete"

# Display running containers
echo ""
log_info "Running containers:"
docker compose ps
