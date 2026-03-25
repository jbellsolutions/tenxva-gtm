#!/bin/bash
# TenXVA GTM — Deploy / Update Script
# Run this after pushing code changes to pull latest + restart

set -e

cd /opt/tenxva-gtm

echo "=== Deploying TenXVA GTM ==="

# Pull latest code (if using git)
# git pull origin main

# Activate venv
source venv/bin/activate

# Update dependencies
pip install -r requirements.txt --quiet

# Restart service
systemctl restart tenxva-gtm

echo "Service restarted. Checking status..."
sleep 2
systemctl status tenxva-gtm --no-pager

echo ""
echo "Logs: journalctl -u tenxva-gtm -f"
