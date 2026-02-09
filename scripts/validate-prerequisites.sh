#!/bin/bash

###############################################################################
# Prerequisite Validation Script
#
# Validates that the system meets all requirements for coordinator installation:
# - System resources (RAM, disk space)
# - Required ports availability
# - DNS configuration
# - Root/sudo access
# - Required system utilities
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
VALIDATION_FAILED=false

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    VALIDATION_FAILED=true
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

echo "Validating prerequisites for Monkey Troop coordinator installation..."
echo ""

# Check 1: Root/Sudo access
log_info "Checking root/sudo access..."
if [[ $EUID -eq 0 ]]; then
    log_success "Running as root"
elif sudo -n true 2>/dev/null; then
    log_success "Sudo access available (passwordless)"
elif sudo -v 2>/dev/null; then
    log_success "Sudo access available"
else
    log_error "Root or sudo access required"
fi
echo ""

# Check 2: System resources
log_info "Checking system resources..."

# RAM check (require at least 2GB)
total_ram_kb=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo "0")
total_ram_gb=$(echo "scale=2; $total_ram_kb / 1024 / 1024" | bc 2>/dev/null || echo "0")

if [[ $(echo "$total_ram_gb >= 2" | bc 2>/dev/null) -eq 1 ]]; then
    log_success "RAM: ${total_ram_gb}GB (minimum 2GB)"
else
    # Try alternative method for non-Linux systems
    if command -v sysctl &> /dev/null; then
        total_ram_bytes=$(sysctl -n hw.memsize 2>/dev/null || echo "0")
        total_ram_gb=$(echo "scale=2; $total_ram_bytes / 1024 / 1024 / 1024" | bc 2>/dev/null || echo "0")
        if [[ $(echo "$total_ram_gb >= 2" | bc 2>/dev/null) -eq 1 ]]; then
            log_success "RAM: ${total_ram_gb}GB (minimum 2GB)"
        else
            log_error "RAM: ${total_ram_gb}GB (minimum 2GB required)"
        fi
    else
        log_warning "Could not determine RAM amount"
    fi
fi

# Disk space check (require at least 20GB free)
if [[ -d "/" ]]; then
    available_gb=$(df -BG / 2>/dev/null | tail -1 | awk '{print $4}' | sed 's/G//' || echo "0")
    if [[ $(echo "$available_gb >= 20" | bc 2>/dev/null) -eq 1 ]]; then
        log_success "Disk space: ${available_gb}GB available (minimum 20GB)"
    else
        log_error "Disk space: ${available_gb}GB available (minimum 20GB required)"
    fi
fi
echo ""

# Check 3: Required ports
log_info "Checking port availability..."

check_port() {
    local port=$1
    local service=$2
    
    if command -v ss &> /dev/null; then
        if ss -tuln | grep -q ":$port "; then
            log_error "Port $port ($service) is already in use"
            return 1
        fi
    elif command -v netstat &> /dev/null; then
        if netstat -tuln 2>/dev/null | grep -q ":$port "; then
            log_error "Port $port ($service) is already in use"
            return 1
        fi
    elif command -v lsof &> /dev/null; then
        if lsof -i ":$port" &>/dev/null; then
            log_error "Port $port ($service) is already in use"
            return 1
        fi
    else
        log_warning "Cannot check port $port ($service) - no suitable tool found"
        return 0
    fi
    
    log_success "Port $port ($service) is available"
    return 0
}

check_port 80 "HTTP"
check_port 443 "HTTPS"
check_port 8000 "Coordinator API"
check_port 8080 "Headscale"
echo ""

# Check 4: DNS configuration
if [[ -n "$DOMAIN" ]]; then
    log_info "Checking DNS configuration..."
    
    check_dns() {
        local hostname=$1
        local record_type=${2:-A}
        
        if command -v dig &> /dev/null; then
            if dig +short "$hostname" "$record_type" | grep -q '^[0-9]'; then
                local ip=$(dig +short "$hostname" "$record_type" | head -1)
                log_success "DNS $record_type record for $hostname: $ip"
                return 0
            else
                log_error "No DNS $record_type record found for $hostname"
                return 1
            fi
        elif command -v nslookup &> /dev/null; then
            if nslookup "$hostname" 2>/dev/null | grep -q "Address:"; then
                log_success "DNS record found for $hostname"
                return 0
            else
                log_error "No DNS record found for $hostname"
                return 1
            fi
        elif command -v host &> /dev/null; then
            if host "$hostname" 2>/dev/null | grep -q "has address"; then
                log_success "DNS record found for $hostname"
                return 0
            else
                log_error "No DNS record found for $hostname"
                return 1
            fi
        else
            log_warning "Cannot check DNS for $hostname - no suitable tool found"
            return 0
        fi
    }
    
    if [[ "$ROUTING_MODE" == "subdomain" ]]; then
        check_dns "api.$DOMAIN"
        check_dns "vpn.$DOMAIN"
    else
        check_dns "$DOMAIN"
    fi
    echo ""
else
    log_warning "No domain specified, skipping DNS validation"
    echo ""
fi

# Check 5: Required system utilities
log_info "Checking required system utilities..."

check_command() {
    local cmd=$1
    local package=$2
    
    if command -v "$cmd" &> /dev/null; then
        log_success "$cmd is installed"
        return 0
    else
        log_error "$cmd is not installed (install package: $package)"
        return 1
    fi
}

check_command "curl" "curl"
check_command "openssl" "openssl"
check_command "tar" "tar"
check_command "bc" "bc"

# Docker will be installed by setup scripts if missing
if command -v docker &> /dev/null; then
    log_success "docker is installed"
else
    log_warning "docker not found (will be installed during setup)"
fi

if command -v docker-compose &> /dev/null || docker compose version &>/dev/null 2>&1; then
    log_success "docker-compose is installed"
else
    log_warning "docker-compose not found (will be installed during setup)"
fi

echo ""

# Check 6: Operating system
log_info "Checking operating system..."
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    log_success "OS: $NAME $VERSION"
    
    case "$ID" in
        ubuntu|debian)
            log_success "Supported OS (Debian-based)"
            ;;
        centos|rhel|fedora)
            log_success "Supported OS (Red Hat-based)"
            ;;
        *)
            log_warning "OS '$ID' may not be fully tested"
            ;;
    esac
else
    log_warning "Could not determine operating system"
fi
echo ""

# Summary
echo "═══════════════════════════════════════════════════════════"
if [[ "$VALIDATION_FAILED" == "true" ]]; then
    echo -e "${RED}Validation Failed${NC}"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "Please resolve the errors above before proceeding."
    echo "You can skip validation with --skip-validation flag (not recommended)."
    exit 1
else
    echo -e "${GREEN}Validation Passed${NC}"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "System meets all requirements for coordinator installation."
fi
