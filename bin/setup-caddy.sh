#!/bin/bash

###############################################################################
# Caddy Reverse Proxy Installation Script
#
# Installs and configures Caddy as a reverse proxy:
# - Automatic HTTPS via Let's Encrypt
# - Routes to coordinator API and Headscale
# - Supports both path-based and subdomain routing
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DOMAIN=""
EMAIL=""
ROUTING_MODE="path"
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
        --email)
            EMAIL="$2"
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

if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
    log_error "Domain and email are required"
fi

log_info "Installing Caddy reverse proxy..."
log_info "Routing mode: $ROUTING_MODE"

# Install Caddy if not present
if ! command -v caddy &> /dev/null; then
    log_info "Installing Caddy..."
    
    if [[ -f /etc/debian_version ]]; then
        # Debian/Ubuntu
        sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
        sudo apt update
        sudo apt install -y caddy
    elif [[ -f /etc/redhat-release ]]; then
        # RHEL/CentOS/Fedora
        sudo yum install -y yum-plugin-copr
        sudo yum copr enable @caddy/caddy -y
        sudo yum install -y caddy
    else
        log_error "Unsupported OS for automatic Caddy installation. Please install Caddy manually."
    fi
    
    log_success "Caddy installed"
else
    log_info "Caddy already installed"
fi

# Stop Caddy if running
sudo systemctl stop caddy 2>/dev/null || true

# Generate Caddyfile based on routing mode
log_info "Generating Caddyfile..."

if [[ "$ROUTING_MODE" == "subdomain" ]]; then
    # Subdomain routing
    if [[ -f "$SCRIPT_DIR/config/Caddyfile.subdomain.template" ]]; then
        sudo cp "$SCRIPT_DIR/config/Caddyfile.subdomain.template" /etc/caddy/Caddyfile
        sudo sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" /etc/caddy/Caddyfile
        sudo sed -i "s/EMAIL_PLACEHOLDER/$EMAIL/g" /etc/caddy/Caddyfile
    else
        sudo tee /etc/caddy/Caddyfile > /dev/null <<EOF
# Caddy configuration for Monkey Troop (Subdomain routing)
{
    email $EMAIL
}

# Coordinator API
api.$DOMAIN {
    reverse_proxy localhost:8000
    
    log {
        output file /var/log/caddy/api.log
    }
}

# Headscale VPN
vpn.$DOMAIN {
    reverse_proxy localhost:8080
    
    log {
        output file /var/log/caddy/vpn.log
    }
}

# Main domain (optional - for marketing site)
$DOMAIN {
    # Serve static files from /var/www/html if they exist
    root * /var/www/html
    file_server
    
    # Or redirect to api subdomain
    # redir https://api.$DOMAIN{uri}
    
    log {
        output file /var/log/caddy/main.log
    }
}
EOF
    fi
else
    # Path-based routing (default)
    if [[ -f "$SCRIPT_DIR/config/Caddyfile.path.template" ]]; then
        sudo cp "$SCRIPT_DIR/config/Caddyfile.path.template" /etc/caddy/Caddyfile
        sudo sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" /etc/caddy/Caddyfile
        sudo sed -i "s/EMAIL_PLACEHOLDER/$EMAIL/g" /etc/caddy/Caddyfile
    else
        sudo tee /etc/caddy/Caddyfile > /dev/null <<EOF
# Caddy configuration for Monkey Troop (Path-based routing)
{
    email $EMAIL
}

$DOMAIN {
    # Coordinator API routes
    handle /api/* {
        reverse_proxy localhost:8000
    }
    
    # Headscale VPN routes
    handle /vpn/* {
        uri strip_prefix /vpn
        reverse_proxy localhost:8080
    }
    
    # Health check endpoint
    handle /health {
        reverse_proxy localhost:8000
    }
    
    # Default: serve static files (marketing site)
    handle {
        root * /var/www/html
        file_server
        
        # Fallback: show a simple page
        respond "Monkey Troop Coordinator" 200
    }
    
    log {
        output file /var/log/caddy/access.log
    }
}
EOF
    fi
fi

log_success "Caddyfile generated"

# Create log directory
sudo mkdir -p /var/log/caddy
sudo chown caddy:caddy /var/log/caddy

# Create web root directory
sudo mkdir -p /var/www/html
sudo tee /var/www/html/index.html > /dev/null <<EOF
<!DOCTYPE html>
<html>
<head>
    <title>Monkey Troop</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            text-align: center;
            padding: 2rem;
        }
        h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        p {
            font-size: 1.2rem;
            opacity: 0.9;
        }
        .api-link {
            margin-top: 2rem;
            padding: 1rem 2rem;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            display: inline-block;
        }
        a {
            color: white;
            text-decoration: none;
            font-weight: 500;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐵 Monkey Troop</h1>
        <p>Distributed AI Inference Network</p>
        <div class="api-link">
            <a href="/api/health">API Status →</a>
        </div>
    </div>
</body>
</html>
EOF

# Validate Caddyfile
log_info "Validating Caddyfile..."
if sudo caddy validate --config /etc/caddy/Caddyfile; then
    log_success "Caddyfile is valid"
else
    log_error "Caddyfile validation failed"
fi

# Start Caddy
log_info "Starting Caddy..."
sudo systemctl enable caddy
sudo systemctl start caddy

# Wait for Caddy to start
sleep 3

# Check if Caddy is running
if systemctl is-active --quiet caddy; then
    log_success "Caddy is running"
else
    log_error "Caddy failed to start. Check: journalctl -u caddy -n 50"
fi

# Test endpoints
log_info "Testing endpoints..."

sleep 5  # Give Caddy time to obtain certificates

if [[ "$ROUTING_MODE" == "subdomain" ]]; then
    # Test subdomain endpoints
    if curl -f -k "https://api.$DOMAIN/health" &>/dev/null || curl -f -k "https://api.$DOMAIN/" &>/dev/null; then
        log_success "Coordinator API endpoint is accessible"
    else
        log_error "Coordinator API endpoint is not accessible"
    fi
else
    # Test path-based endpoints
    if curl -f -k "https://$DOMAIN/api/health" &>/dev/null || curl -f -k "https://$DOMAIN/health" &>/dev/null; then
        log_success "Coordinator API endpoint is accessible"
    else
        log_error "Coordinator API endpoint is not accessible"
    fi
fi

log_success "Caddy reverse proxy installation complete"

echo ""
log_info "SSL certificates will be automatically obtained from Let's Encrypt"
log_info "This may take a few moments on first access"
