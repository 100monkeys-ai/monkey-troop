# Coordinator Installation System - Testing Guide

## Overview

This testing guide helps verify the automated coordinator installation system works correctly.

## What Was Built

### Main Installation Script
- `install-coordinator.sh` - Main orchestration script (15KB)
  - Interactive prompts with sensible defaults
  - CLI flag support for automation
  - Path-based routing (default) and subdomain routing
  - Optional automated backups with rolling retention

### Setup Scripts (scripts/)
- `validate-prerequisites.sh` - System requirement validation
- `setup-headscale.sh` - Headscale VPN installation
- `setup-coordinator-stack.sh` - Docker stack deployment
- `setup-caddy.sh` - Reverse proxy with automatic HTTPS
- `setup-backups.sh` - Automated database backups

### Configuration Templates (config/)
- `headscale.yaml.template` - Headscale VPN configuration
- `Caddyfile.path.template` - Path-based routing (https://DOMAIN/api, /vpn)
- `Caddyfile.subdomain.template` - Subdomain routing (https://api.DOMAIN, vpn.DOMAIN)

### Systemd Services (systemd/)
- `headscale.service` - Headscale daemon
- `coordinator-stack.service` - Docker Compose coordinator
- `troop-backup.service` - Backup execution
- `troop-backup.timer` - Daily backup scheduler (02:00)

## Testing on a VPS

### Prerequisites

1. **Fresh VPS** (Ubuntu 22.04 or Debian 12 recommended)
   - Minimum: 2GB RAM, 20GB disk, 2 vCPUs
   - Root or sudo access

2. **Domain with DNS configured**
   - For path-based: A record for `example.com` → VPS IP
   - For subdomain: A records for `api.example.com` and `vpn.example.com` → VPS IP

3. **Ports open**
   - 80/tcp (HTTP)
   - 443/tcp (HTTPS)
   - 8000/tcp (Coordinator API - internal)
   - 8080/tcp (Headscale - internal)

### Test Case 1: Interactive Installation (Path-based)

```bash
# SSH to VPS
ssh root@your-vps-ip

# Clone repository
git clone https://github.com/100monkeys-ai/monkey-troop.git
cd monkey-troop

# Run interactive installer
./install-coordinator.sh

# Follow prompts:
# - Domain: troop.example.com
# - Email: admin@example.com
# - Routing mode: 1 (path-based)
# - Enable backups: y
# - Retention days: 7
```

**Expected Output:**
- ✅ Prerequisites validated
- ✅ Headscale installed and running
- ✅ Coordinator stack deployed
- ✅ Caddy configured with HTTPS
- ✅ Backups scheduled
- 🔑 Admin password displayed
- 🔑 Pre-auth key generated
- 📍 URLs shown: https://troop.example.com/api, /vpn

**Verification:**
```bash
# Check services
systemctl status headscale
systemctl status coordinator-stack
systemctl status caddy
systemctl list-timers troop-backup.timer

# Test endpoints
curl https://troop.example.com/health
curl https://troop.example.com/api/health
headscale nodes list

# Check logs
journalctl -u headscale -n 50
docker logs troop-coordinator
journalctl -u caddy -n 50
```

### Test Case 2: Automated Installation (Subdomain)

```bash
# SSH to VPS
ssh root@your-vps-ip

# Clone repository
cd monkey-troop

# Run with CLI flags
./install-coordinator.sh \
  --domain example.com \
  --email admin@example.com \
  --routing-mode subdomain \
  --enable-backups \
  --backup-retention-days 14 \
  --db-password "MySecureDBPass123!" \
  --admin-password "MySecureAdminPass123!"
```

**Expected Output:**
- Same as Test Case 1 but non-interactive
- URLs: https://api.example.com, https://vpn.example.com

**Verification:**
```bash
# Test subdomain endpoints
curl https://api.example.com/health
curl https://vpn.example.com/

# Check environment
cat /opt/monkey-troop/.env | grep COORDINATOR_URL
# Should show: COORDINATOR_URL=https://api.example.com

# Test backup
sudo /usr/local/bin/backup-troop-db.sh
ls -lh /var/backups/troop/
```

### Test Case 3: Skip Validation

```bash
# For testing in environments where validation might fail
./install-coordinator.sh \
  --domain test.example.com \
  --email test@example.com \
  --skip-validation
```

### Test Case 4: Worker Registration

After coordinator is running, test worker connection:

```bash
# On worker machine
curl -fsSL https://raw.githubusercontent.com/100monkeys-ai/monkey-troop/main/install.sh | bash

# Use the pre-auth key from coordinator installation output
export COORDINATOR_URL="https://troop.example.com/api"
export TS_AUTHKEY="<key-from-coordinator-output>"

# Connect to VPN
tailscale up --login-server=https://troop.example.com/vpn --authkey=$TS_AUTHKEY

# Verify connection
tailscale status

# On coordinator, verify node appeared
headscale nodes list
```

## Manual Testing Checklist

### Before Installation
- [ ] VPS has sufficient resources (2GB RAM, 20GB disk)
- [ ] DNS records are configured and propagated
- [ ] Ports 80, 443 are accessible
- [ ] Root/sudo access available

### During Installation
- [ ] Script prompts for all required values
- [ ] Validation passes (or skip flag works)
- [ ] No errors during Headscale installation
- [ ] Docker containers start successfully
- [ ] Caddy obtains Let's Encrypt certificates
- [ ] Admin password and pre-auth key displayed
- [ ] Instructions printed clearly

### After Installation
- [ ] Coordinator API responds: `curl https://DOMAIN/api/health`
- [ ] Headscale endpoint accessible: `curl https://DOMAIN/vpn/`
- [ ] Services are running: `systemctl status headscale coordinator-stack caddy`
- [ ] Services auto-restart on failure: `systemctl restart coordinator-stack`
- [ ] Logs are accessible: `journalctl -u headscale`
- [ ] Backups are scheduled: `systemctl list-timers`
- [ ] Can generate new keys: `headscale preauthkeys create --namespace default`
- [ ] Workers can connect using pre-auth key

### Backup Testing
- [ ] Run manual backup: `sudo /usr/local/bin/backup-troop-db.sh`
- [ ] Backup file created: `ls /var/backups/troop/`
- [ ] Backup is compressed: `.sql.gz` extension
- [ ] Log file updated: `cat /var/log/troop-backups.log`
- [ ] Timer is active: `systemctl status troop-backup.timer`
- [ ] Old backups deleted after retention period

### Error Recovery Testing
- [ ] Stop coordinator: `systemctl stop coordinator-stack`
- [ ] Verify auto-restart: `systemctl status coordinator-stack` (should restart)
- [ ] Stop Headscale: `systemctl stop headscale`
- [ ] Verify auto-restart: `systemctl status headscale`
- [ ] Kill Caddy: `sudo killall caddy`
- [ ] Verify auto-restart: `systemctl status caddy`

## Common Issues & Solutions

### Issue: DNS not resolving
**Solution:** Wait for DNS propagation (up to 48 hours). Use `dig DOMAIN` to check.

### Issue: Port already in use
**Solution:** Run prerequisite validation to identify conflicting services.

### Issue: Let's Encrypt rate limit
**Solution:** Use Caddy's staging environment or wait 1 hour. Check: `journalctl -u caddy`

### Issue: Docker not found
**Solution:** The script auto-installs Docker. If it fails, install manually first.

### Issue: Headscale service won't start
**Solution:** Check logs: `journalctl -u headscale -n 100` and verify config: `headscale serve` manually.

### Issue: Coordinator containers not healthy
**Solution:** Check logs: `docker logs troop-coordinator troop-postgres troop-redis`

## Cleanup (Reset Test Environment)

```bash
# Stop all services
systemctl stop caddy headscale coordinator-stack troop-backup.timer

# Remove Docker containers
cd /opt/monkey-troop
docker compose down -v

# Remove installed files
rm -rf /opt/monkey-troop
rm -rf /etc/headscale
rm -rf /var/lib/headscale
rm -rf /var/run/headscale
rm -f /usr/local/bin/headscale
rm -f /usr/local/bin/backup-troop-db.sh
rm -rf /var/backups/troop
rm -f /var/log/troop-backups.log

# Remove systemd services
rm -f /etc/systemd/system/headscale.service
rm -f /etc/systemd/system/coordinator-stack.service
rm -f /etc/systemd/system/troop-backup.service
rm -f /etc/systemd/system/troop-backup.timer
systemctl daemon-reload

# Remove Caddy config (if you want to keep Caddy for other uses, just edit the file)
rm -f /etc/caddy/Caddyfile
systemctl reload caddy

# Repository can be kept or removed
rm -rf ~/monkey-troop
```

## Success Criteria

Installation is successful when:

1. ✅ All systemd services are `active (running)`
2. ✅ Coordinator API responds to health checks
3. ✅ Headscale VPN endpoint is accessible
4. ✅ HTTPS certificates are obtained automatically
5. ✅ Workers can connect using pre-auth key
6. ✅ Database backups run and old ones are cleaned up
7. ✅ Services auto-restart on failure
8. ✅ No errors in service logs

## Performance Expectations

- **Installation time:** 5-10 minutes (depending on VPS speed and network)
- **First HTTPS cert:** 30-60 seconds after Caddy starts
- **Coordinator API startup:** 10-20 seconds (includes migrations)
- **Headscale startup:** 2-5 seconds
- **Memory usage:** ~1.2GB for all services combined
- **Disk usage:** ~2-3GB (plus backups grow over time)

## Security Notes

- Admin password and DB password are auto-generated (secure random)
- Pre-auth keys are valid for 90 days and reusable
- All traffic uses HTTPS (automatic Let's Encrypt)
- Coordinator internal ports (8000, 8080) only accessible via reverse proxy
- Systemd services include hardening (NoNewPrivileges, PrivateTmp, etc.)
- Backup files are chmod 600 (only root can read)

## Next Steps After Successful Installation

1. **Save credentials** - Store admin password and DB password in a password manager
2. **Generate more keys** - Create pre-auth keys for different user groups
3. **Setup monitoring** - Add external monitoring for uptime
4. **Configure firewall** - Use ufw or firewalld for additional security
5. **Setup offsite backups** - Copy `/var/backups/troop/` to S3 or another location
6. **Update DNS** - Add proper DNS records (A, AAAA, CAA)
7. **Join the network** - Have workers connect using the installation guide

---

**Questions or Issues?**
- Check logs first: `journalctl -u SERVICE_NAME -n 100`
- Review DEPLOYMENT.md for detailed documentation
- Open an issue on GitHub with logs and error messages
