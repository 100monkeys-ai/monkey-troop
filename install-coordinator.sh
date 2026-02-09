#!/bin/bash

###############################################################################
# Monkey Troop Coordinator Installation Script
# 
# This script automates the deployment of a Monkey Troop coordinator hub,
# including Headscale VPN server, coordinator API, PostgreSQL database,
# Redis cache, and Caddy reverse proxy.
#
# Target Audience: Network operators deploying the centralized hub
# End Users: Use install.sh instead for worker/client installation
#
# Usage:
#   ./install-coordinator.sh                    # Interactive mode
#   ./install-coordinator.sh --domain example.com --email admin@example.com
#
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default values
ROUTING_MODE="path"
ENABLE_BACKUPS="false"
BACKUP_RETENTION_DAYS="7"
DOMAIN=""
EMAIL=""
DB_PASSWORD=""
ADMIN_PASSWORD=""

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_banner() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                                                           ║"
    echo "║         Monkey Troop Coordinator Installation            ║"
    echo "║                                                           ║"
    echo "║  Deploy a complete coordinator hub with Headscale VPN    ║"
    echo "║                                                           ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
}

print_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Network Operator Installation - Deploy Coordinator Hub

OPTIONS:
    --domain DOMAIN              Domain name (e.g., example.com)
    --email EMAIL               Email for Let's Encrypt certificates
    --routing-mode MODE         Routing mode: 'path' or 'subdomain' (default: path)
    --db-password PASSWORD      PostgreSQL database password (auto-generated if not provided)
    --admin-password PASSWORD   Coordinator admin password (auto-generated if not provided)
    --enable-backups            Enable automated database backups
    --backup-retention-days N   Number of days to retain backups (default: 7)
    --skip-validation           Skip prerequisite validation checks
    -h, --help                  Display this help message

EXAMPLES:
    # Interactive mode (recommended for first-time setup)
    ./install-coordinator.sh

    # Automated mode with all parameters
    ./install-coordinator.sh \\
        --domain troop.example.com \\
        --email admin@example.com \\
        --routing-mode path \\
        --enable-backups \\
        --backup-retention-days 14

ROUTING MODES:
    path (default):
        - Coordinator API: https://DOMAIN/api
        - Headscale VPN:   https://DOMAIN/vpn
        - Works well with marketing site at https://DOMAIN

    subdomain:
        - Coordinator API: https://api.DOMAIN
        - Headscale VPN:   https://vpn.DOMAIN
        - Requires separate DNS A records for subdomains

NOTES:
    - This script requires root/sudo access
    - Ensure DNS records are configured before running
    - For end-user worker/client installation, use install.sh instead

EOF
}

# Parse command line arguments
parse_args() {
    SKIP_VALIDATION="false"
    
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
                if [[ "$ROUTING_MODE" != "path" && "$ROUTING_MODE" != "subdomain" ]]; then
                    log_error "Invalid routing mode: $ROUTING_MODE (must be 'path' or 'subdomain')"
                    exit 1
                fi
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
            --enable-backups)
                ENABLE_BACKUPS="true"
                shift
                ;;
            --backup-retention-days)
                BACKUP_RETENTION_DAYS="$2"
                shift 2
                ;;
            --skip-validation)
                SKIP_VALIDATION="true"
                shift
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done
}

# Interactive prompts for missing values
interactive_prompts() {
    log_info "Starting interactive setup..."
    echo ""
    
    # Domain
    if [[ -z "$DOMAIN" ]]; then
        read -p "Enter your domain name (e.g., troop.example.com): " DOMAIN
        if [[ -z "$DOMAIN" ]]; then
            log_error "Domain is required"
            exit 1
        fi
    fi
    
    # Email
    if [[ -z "$EMAIL" ]]; then
        read -p "Enter email for Let's Encrypt certificates: " EMAIL
        if [[ -z "$EMAIL" ]]; then
            log_error "Email is required"
            exit 1
        fi
    fi
    
    # Routing mode
    echo ""
    log_info "Choose routing mode:"
    echo "  1) Path-based (default) - API at /$DOMAIN/api, VPN at /$DOMAIN/vpn"
    echo "  2) Subdomain - API at api.$DOMAIN, VPN at vpn.$DOMAIN"
    read -p "Enter choice [1-2] (default: 1): " routing_choice
    case $routing_choice in
        2)
            ROUTING_MODE="subdomain"
            ;;
        *)
            ROUTING_MODE="path"
            ;;
    esac
    
    # Backups
    echo ""
    read -p "Enable automated database backups? [y/N]: " enable_backups_choice
    if [[ "$enable_backups_choice" =~ ^[Yy]$ ]]; then
        ENABLE_BACKUPS="true"
        read -p "Backup retention days (default: 7): " retention_input
        if [[ -n "$retention_input" ]]; then
            BACKUP_RETENTION_DAYS="$retention_input"
        fi
    fi
    
    echo ""
}

# Generate secure passwords
generate_passwords() {
    if [[ -z "$DB_PASSWORD" ]]; then
        DB_PASSWORD=$(openssl rand -hex 32)
        log_info "Generated secure database password"
    fi
    
    if [[ -z "$ADMIN_PASSWORD" ]]; then
        ADMIN_PASSWORD=$(openssl rand -hex 32)
        log_info "Generated secure admin password"
    fi
}

# Print configuration summary
print_summary() {
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "Configuration Summary"
    echo "═══════════════════════════════════════════════════════════"
    echo "Domain:           $DOMAIN"
    echo "Email:            $EMAIL"
    echo "Routing Mode:     $ROUTING_MODE"
    
    if [[ "$ROUTING_MODE" == "path" ]]; then
        echo "Coordinator URL:  https://$DOMAIN/api"
        echo "Headscale URL:    https://$DOMAIN/vpn"
    else
        echo "Coordinator URL:  https://api.$DOMAIN"
        echo "Headscale URL:    https://vpn.$DOMAIN"
    fi
    
    echo "Backups Enabled:  $ENABLE_BACKUPS"
    if [[ "$ENABLE_BACKUPS" == "true" ]]; then
        echo "Retention Days:   $BACKUP_RETENTION_DAYS"
    fi
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    
    read -p "Proceed with installation? [y/N]: " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "Installation cancelled by user"
        exit 0
    fi
}

# Main installation sequence
main() {
    print_banner
    parse_args "$@"
    interactive_prompts
    generate_passwords
    print_summary
    
    log_info "Starting Monkey Troop coordinator installation..."
    echo ""
    
    # Step 1: Validate prerequisites
    if [[ "$SKIP_VALIDATION" != "true" ]]; then
        log_info "Step 1/5: Validating prerequisites..."
        bash "$SCRIPT_DIR/scripts/validate-prerequisites.sh" \
            --domain "$DOMAIN" \
            --routing-mode "$ROUTING_MODE"
        log_success "Prerequisites validated"
        echo ""
    else
        log_warning "Skipping prerequisite validation"
        echo ""
    fi
    
    # Step 2: Setup Headscale
    log_info "Step 2/5: Installing Headscale VPN server..."
    TS_AUTHKEY=$(bash "$SCRIPT_DIR/scripts/setup-headscale.sh" \
        --domain "$DOMAIN" \
        --routing-mode "$ROUTING_MODE")
    log_success "Headscale installed successfully"
    echo ""
    
    # Step 3: Setup Coordinator Stack
    log_info "Step 3/5: Installing Coordinator stack..."
    bash "$SCRIPT_DIR/scripts/setup-coordinator-stack.sh" \
        --domain "$DOMAIN" \
        --routing-mode "$ROUTING_MODE" \
        --db-password "$DB_PASSWORD" \
        --admin-password "$ADMIN_PASSWORD"
    log_success "Coordinator stack installed successfully"
    echo ""
    
    # Step 4: Setup Caddy reverse proxy
    log_info "Step 4/5: Installing Caddy reverse proxy..."
    bash "$SCRIPT_DIR/scripts/setup-caddy.sh" \
        --domain "$DOMAIN" \
        --email "$EMAIL" \
        --routing-mode "$ROUTING_MODE"
    log_success "Caddy reverse proxy installed successfully"
    echo ""
    
    # Step 5: Setup backups (optional)
    if [[ "$ENABLE_BACKUPS" == "true" ]]; then
        log_info "Step 5/5: Setting up automated backups..."
        bash "$SCRIPT_DIR/scripts/setup-backups.sh" \
            --retention-days "$BACKUP_RETENTION_DAYS" \
            --db-password "$DB_PASSWORD"
        log_success "Backup automation configured"
        echo ""
    else
        log_info "Step 5/5: Skipping backup setup (not enabled)"
        echo ""
    fi
    
    # Print final information
    print_completion_info
}

# Print completion information
print_completion_info() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                                                           ║"
    echo "║         Installation Complete! 🎉                        ║"
    echo "║                                                           ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
    echo "Your Monkey Troop coordinator hub is now running!"
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "ACCESS INFORMATION"
    echo "═══════════════════════════════════════════════════════════"
    
    if [[ "$ROUTING_MODE" == "path" ]]; then
        echo "Coordinator API:  https://$DOMAIN/api"
        echo "Headscale VPN:    https://$DOMAIN/vpn"
    else
        echo "Coordinator API:  https://api.$DOMAIN"
        echo "Headscale VPN:    https://vpn.$DOMAIN"
    fi
    
    echo ""
    echo "Admin Credentials:"
    echo "  Username: admin"
    echo "  Password: $ADMIN_PASSWORD"
    echo ""
    echo "Database Password: $DB_PASSWORD"
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "WORKER REGISTRATION"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "Workers can now join your network using this pre-auth key:"
    echo ""
    echo "  $TS_AUTHKEY"
    echo ""
    echo "Workers should run:"
    
    if [[ "$ROUTING_MODE" == "path" ]]; then
        echo "  curl -fsSL https://raw.githubusercontent.com/100monkeys-ai/monkey-troop/main/install.sh | bash"
        echo "  export COORDINATOR_URL=\"https://$DOMAIN/api\""
        echo "  export TS_AUTHKEY=\"$TS_AUTHKEY\""
        echo "  tailscale up --login-server=https://$DOMAIN/vpn --authkey=\$TS_AUTHKEY"
    else
        echo "  curl -fsSL https://raw.githubusercontent.com/100monkeys-ai/monkey-troop/main/install.sh | bash"
        echo "  export COORDINATOR_URL=\"https://api.$DOMAIN\""
        echo "  export TS_AUTHKEY=\"$TS_AUTHKEY\""
        echo "  tailscale up --login-server=https://vpn.$DOMAIN --authkey=\$TS_AUTHKEY"
    fi
    
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "IMPORTANT NOTES"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "1. Save your admin password and database password securely"
    echo "2. The pre-auth key can be used to register multiple workers"
    echo "3. Generate new pre-auth keys with: headscale preauthkeys create"
    echo "4. View registered nodes with: headscale nodes list"
    
    if [[ "$ENABLE_BACKUPS" == "true" ]]; then
        echo "5. Database backups are stored in: /var/backups/troop/"
        echo "6. Backup retention: $BACKUP_RETENTION_DAYS days"
    else
        echo "5. Database backups are NOT enabled (run with --enable-backups)"
    fi
    
    echo ""
    echo "View logs:"
    echo "  Coordinator:  docker logs -f troop-coordinator"
    echo "  Headscale:    journalctl -u headscale -f"
    echo "  Caddy:        journalctl -u caddy -f"
    
    if [[ "$ENABLE_BACKUPS" == "true" ]]; then
        echo "  Backups:      cat /var/log/troop-backups.log"
    fi
    
    echo ""
    echo "Documentation: $SCRIPT_DIR/docs/DEPLOYMENT.md"
    echo ""
}

# Run main function
main "$@"
