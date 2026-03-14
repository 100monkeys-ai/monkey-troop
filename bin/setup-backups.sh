#!/bin/bash

###############################################################################
# Database Backup Setup Script
#
# Configures automated PostgreSQL backups with rolling retention:
# - Creates backup script
# - Configures systemd timer for daily execution
# - Implements rolling retention policy
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

RETENTION_DAYS="7"
DB_PASSWORD=""
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
        --retention-days)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --db-password)
            DB_PASSWORD="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

if [[ -z "$DB_PASSWORD" ]]; then
    log_error "Database password is required"
fi

log_info "Setting up automated database backups..."
log_info "Retention policy: $RETENTION_DAYS days"

# Create backup directory
BACKUP_DIR="/var/backups/troop"
sudo mkdir -p "$BACKUP_DIR"
sudo chmod 700 "$BACKUP_DIR"

log_success "Backup directory created: $BACKUP_DIR"

# Create backup script
log_info "Creating backup script..."

sudo tee /usr/local/bin/backup-troop-db.sh > /dev/null <<'EOF'
#!/bin/bash

###############################################################################
# Monkey Troop Database Backup Script
#
# Performs PostgreSQL backup with compression and rolling retention
###############################################################################

set -e

# Configuration
BACKUP_DIR="/var/backups/troop"
LOG_FILE="/var/log/troop-backups.log"
RETENTION_DAYS="RETENTION_DAYS_PLACEHOLDER"
DB_PASSWORD="DB_PASSWORD_PLACEHOLDER"
DB_CONTAINER="troop-postgres"
DB_NAME="troop_ledger"
DB_USER="troop_admin"

# Timestamp
TIMESTAMP=$(date +"%Y-%m-%d-%H%M%S")
BACKUP_FILE="$BACKUP_DIR/db-$TIMESTAMP.sql.gz"

# Log function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "Starting backup: $BACKUP_FILE"

# Check if container is running
if ! docker ps | grep -q "$DB_CONTAINER"; then
    log "ERROR: Database container is not running"
    exit 1
fi

# Perform backup
if docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Backup completed successfully: $BACKUP_FILE ($BACKUP_SIZE)"
else
    log "ERROR: Backup failed"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Set permissions
chmod 600 "$BACKUP_FILE"

# Implement rolling retention - delete old backups
log "Cleaning up old backups (retention: $RETENTION_DAYS days)"

DELETED_COUNT=0
while IFS= read -r old_backup; do
    if [[ -f "$old_backup" ]]; then
        rm -f "$old_backup"
        log "Deleted old backup: $(basename "$old_backup")"
        DELETED_COUNT=$((DELETED_COUNT + 1))
    fi
done < <(find "$BACKUP_DIR" -name "db-*.sql.gz" -type f -mtime +"$RETENTION_DAYS")

if [[ $DELETED_COUNT -gt 0 ]]; then
    log "Deleted $DELETED_COUNT old backup(s)"
else
    log "No old backups to delete"
fi

# Summary
TOTAL_BACKUPS=$(find "$BACKUP_DIR" -name "db-*.sql.gz" -type f | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "Backup summary: $TOTAL_BACKUPS backup(s) stored, total size: $TOTAL_SIZE"
log "Backup completed"
EOF

# Replace placeholders
sudo sed -i "s/RETENTION_DAYS_PLACEHOLDER/$RETENTION_DAYS/g" /usr/local/bin/backup-troop-db.sh
sudo sed -i "s/DB_PASSWORD_PLACEHOLDER/$DB_PASSWORD/g" /usr/local/bin/backup-troop-db.sh

# Make script executable
sudo chmod 755 /usr/local/bin/backup-troop-db.sh

log_success "Backup script created: /usr/local/bin/backup-troop-db.sh"

# Create log file
sudo touch /var/log/troop-backups.log
sudo chmod 644 /var/log/troop-backups.log

# Install systemd service
log_info "Installing systemd service..."

if [[ -f "$SCRIPT_DIR/systemd/troop-backup.service" ]]; then
    sudo cp "$SCRIPT_DIR/systemd/troop-backup.service" /etc/systemd/system/troop-backup.service
else
    sudo tee /etc/systemd/system/troop-backup.service > /dev/null <<EOF
[Unit]
Description=Monkey Troop Database Backup
Requires=docker.service coordinator-stack.service
After=docker.service coordinator-stack.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/backup-troop-db.sh
User=root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
fi

# Install systemd timer
log_info "Installing systemd timer..."

if [[ -f "$SCRIPT_DIR/systemd/troop-backup.timer" ]]; then
    sudo cp "$SCRIPT_DIR/systemd/troop-backup.timer" /etc/systemd/system/troop-backup.timer
else
    sudo tee /etc/systemd/system/troop-backup.timer > /dev/null <<EOF
[Unit]
Description=Monkey Troop Database Backup Timer
Requires=troop-backup.service

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
fi

# Enable and start timer
log_info "Enabling backup timer..."
sudo systemctl daemon-reload
sudo systemctl enable troop-backup.timer
sudo systemctl start troop-backup.timer

# Verify timer is active
if systemctl is-active --quiet troop-backup.timer; then
    log_success "Backup timer is active"
else
    log_error "Backup timer failed to start"
fi

# Show timer status
echo ""
log_info "Timer status:"
sudo systemctl list-timers troop-backup.timer --no-pager

# Run initial backup
echo ""
read -p "Run initial backup now? [y/N]: " run_backup
if [[ "$run_backup" =~ ^[Yy]$ ]]; then
    log_info "Running initial backup..."
    if sudo /usr/local/bin/backup-troop-db.sh; then
        log_success "Initial backup completed"
        echo ""
        log_info "Backup created:"
        ls -lh "$BACKUP_DIR"/db-*.sql.gz | tail -1
    else
        log_error "Initial backup failed"
    fi
fi

echo ""
log_success "Backup automation setup complete"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "BACKUP INFORMATION"
echo "═══════════════════════════════════════════════════════════"
echo "Backup Directory:  $BACKUP_DIR"
echo "Backup Schedule:   Daily at 02:00"
echo "Retention:         $RETENTION_DAYS days"
echo "Log File:          /var/log/troop-backups.log"
echo ""
echo "Manual Commands:"
echo "  Run backup:      sudo /usr/local/bin/backup-troop-db.sh"
echo "  View backups:    ls -lh $BACKUP_DIR"
echo "  View logs:       cat /var/log/troop-backups.log"
echo "  Timer status:    systemctl status troop-backup.timer"
echo ""
echo "Restore Database:"
echo "  gunzip -c $BACKUP_DIR/db-YYYY-MM-DD-HHMMSS.sql.gz | \\"
echo "    docker exec -i troop-postgres psql -U troop_admin troop_ledger"
echo "═══════════════════════════════════════════════════════════"
