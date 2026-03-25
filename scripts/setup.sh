#!/bin/bash
# TenXVA GTM System — DigitalOcean Droplet Setup Script
# Run this once on a fresh Ubuntu 22.04+ droplet

set -e

echo "=== TenXVA GTM Setup ==="

# Update system
apt-get update && apt-get upgrade -y

# Install Python 3.11+
apt-get install -y python3 python3-pip python3-venv git

# Create app directory
mkdir -p /opt/tenxva-gtm
cd /opt/tenxva-gtm

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create data directories
mkdir -p data/{swipe-file,trend-intel,briefs,drafts,published,influencers/{content,analysis},leads,engagement/{incoming,replies,outbound},analytics}

# Create .env file template
cat > .env << 'ENVEOF'
# TenXVA GTM — Environment Variables
# Fill in your API keys below

ANTHROPIC_API_KEY=your_key_here
FIRECRAWL_API_KEY=your_key_here
APIFY_API_TOKEN=your_token_here
PHANTOMBUSTER_API_KEY=your_key_here
RETRIEVER_API_KEY=your_key_here

# PhantomBuster Phantom IDs (set up phantoms in PB dashboard first)
PB_POST_PHANTOM_ID=
PB_REPLY_PHANTOM_ID=
PB_COMMENT_PHANTOM_ID=
ENVEOF

echo "Edit .env with your API keys: nano /opt/tenxva-gtm/.env"

# Create systemd service
cat > /etc/systemd/system/tenxva-gtm.service << 'SVCEOF'
[Unit]
Description=TenXVA GTM Content Agent System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tenxva-gtm
EnvironmentFile=/opt/tenxva-gtm/.env
ExecStart=/opt/tenxva-gtm/venv/bin/python main.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
SVCEOF

# Enable service
systemctl daemon-reload
systemctl enable tenxva-gtm

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Edit .env with your API keys:  nano /opt/tenxva-gtm/.env"
echo "2. Copy the swipe file data to:   /opt/tenxva-gtm/data/swipe-file/"
echo "3. Start the service:             systemctl start tenxva-gtm"
echo "4. Check logs:                    journalctl -u tenxva-gtm -f"
echo "5. Test manually:                 python main.py --run content"
