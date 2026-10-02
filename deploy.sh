#!/bin/bash

# ICT-ML Trading System - Deployment Script
# This script deploys the system to a production server (VPS)

set -e

echo "=================================================="
echo "ICT-ML Trading System - Deployment Script"
echo "=================================================="
echo "Started at: $(date)"
echo ""

# Configuration
PROJECT_DIR="/opt/ict-trading"
DEPLOY_USER="appuser"
APP_NAME="ict-trading"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root or with sudo${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found!${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}Please edit .env with your credentials!${NC}"
fi

# Create application directory
echo -e "${GREEN}[1/8] Creating application directory...${NC}"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# Copy application files
echo -e "${GREEN}[2/8] Copying application files...${NC}"
cp -r /app/loyiha/* ./

# Create virtual environment
echo -e "${GREEN}[3/8] Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# Install dependencies
echo -e "${GREEN}[4/8] Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Initialize database
echo -e "${GREEN}[5/8] Initializing database...${NC}"
source venv/bin/activate
python3 -c "from data.database import init_db; init_db()"

# Set permissions
echo -e "${GREEN}[6/8] Setting permissions...${NC}"
chown -R $DEPLOY_USER:$DEPLOY_USER $PROJECT_DIR

# Create systemd service
echo -e "${GREEN}[7/8] Creating systemd service...${NC}"
cat > /etc/systemd/system/$APP_NAME.service << EOF
[Unit]
Description=ICT-ML Trading System
After=network.target

[Service]
User=$DEPLOY_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=$APP_NAME

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable $APP_NAME
systemctl restart $APP_NAME

echo -e "${GREEN}[8/8] Deployment completed!${NC}"
echo ""
echo "=================================================="
echo "Deployment Summary"
echo "=================================================="
echo "Project directory: $PROJECT_DIR"
echo "Service status: systemctl status $APP_NAME"
echo "Logs: journalctl -u $APP_NAME -f"
echo "=================================================="
echo ""
echo -e "${GREEN}Deployment successful!${NC}"
echo ""
echo "Next steps:"
echo "1. Check service status: systemctl status $APP_NAME"
echo "2. View logs: journalctl -u $APP_NAME -f"
echo "3. Test bot in Telegram"
echo ""
