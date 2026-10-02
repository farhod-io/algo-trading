# Deployment Guide - ICT-ML Trading System

## Quick Start (Local Development)

```bash
cd loyiha

# 1. Copy environment template
cp .env.example .env

# 2. Edit .env with your credentials
nano .env
# - Add your TELEGRAM_BOT_TOKEN
# - Add your TELEGRAM_CHAT_ID
# - Optionally add API keys for live trading

# 3. Install dependencies (if not already installed)
pip install -r requirements.txt

# 4. Initialize database
python3 -c "from data.database import init_db; init_db()"

# 5. Start the bot
python3 main.py
```

## Production Deployment (VPS)

### Prerequisites
- Ubuntu 20.04+ or Debian 11+
- Root access
- Minimum 2GB RAM, 20GB disk space
- Domain name (optional, for webhook mode)

### Automated Deployment

```bash
# Clone the repository
git clone https://github.com/your-username/algo-trading.git
cd algo-trading

# Make scripts executable
chmod +x deploy.sh health_check.sh

# Run deployment script
sudo ./deploy.sh
```

### Manual Deployment

```bash
# 1. Create application user
sudo useradd -m -u 1000 appuser

# 2. Create application directory
sudo mkdir -p /opt/ict-trading
sudo chown appuser:appuser /opt/ict-trading

# 3. Copy application files
sudo cp -r loyiha/* /opt/ict-trading/

# 4. Install Python dependencies
cd /opt/ict-trading
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
# Edit .env with your credentials
nano .env

# 6. Initialize database
python3 -c "from data.database import init_db; init_db()"

# 7. Create systemd service
sudo tee /etc/systemd/system/ict-trading.service << EOF
[Unit]
Description=ICT-ML Trading System
After=network.target

[Service]
User=appuser
WorkingDirectory=/opt/ict-trading
Environment="PATH=/opt/ict-trading/venv/bin"
EnvironmentFile=/opt/ict-trading/.env
ExecStart=/opt/ict-trading/venv/bin/python3 /opt/ict-trading/main.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=ict-trading

[Install]
WantedBy=multi-user.target
EOF

# 8. Start service
sudo systemctl daemon-reload
sudo systemctl enable ict-trading
sudo systemctl start ict-trading

# 9. Verify service status
sudo systemctl status ict-trading
```

### Webhook Deployment (Production)

For production with webhook mode:

```bash
# 1. Configure webhook in .env
nano /opt/ict-trading/.env
```

Add:
```env
USE_WEBHOOK=true
WEBHOOK_URL=https://your-domain.com/your-bot-token
WEBHOOK_PORT=8443
WEBHOOK_LISTEN=0.0.0.0
```

```bash
# 2. Configure firewall
sudo ufw allow 8443/tcp

# 3. Restart service
sudo systemctl restart ict-trading

# 4. Check logs
sudo journalctl -u ict-trading -f
```

## Monitoring

### Health Check

```bash
# Run health check script
sudo ./health_check.sh

# Or manually check
sudo systemctl status ict-trading
sudo journalctl -u ict-trading --since "1 hour ago"
```

### View Logs

```bash
# Real-time logs
sudo journalctl -u ict-trading -f

# Filter errors
sudo journalctl -u ict-trading | grep ERROR

# View dashboard
curl http://localhost:5000
```

### Restart Service

```bash
sudo systemctl restart ict-trading
```

### Update Application

```bash
cd /path/to/algo-trading
git pull origin main

# Update dependencies if needed
cd /opt/ict-trading
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Restart service
sudo systemctl restart ict-trading
```

## Docker Deployment

### Build Docker Image

```bash
# Build the image
docker build -t ict-trading:latest .

# Or build with specific tag
docker build -t ict-trading:v1.0.0 .
```

### Run Container

```bash
docker run -d \
  --name ict-trading \
  -v /path/to/data:/app/data \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e TELEGRAM_CHAT_ID=your_chat_id \
  -p 5000:5000 \
  --restart unless-stopped \
  ict-trading:latest
```

### Docker Compose

```yaml
version: '3.8'

services:
  ict-trading:
    build: .
    container_name: ict-trading
    restart: unless-stopped
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
      - DATABASE_URL=sqlite:///./signals.db
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "python3", "-c", "from data.database import init_db; init_db()"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Troubleshooting

### Bot doesn't start

```bash
# Check logs
sudo journalctl -u ict-trading -n 50

# Check .env file
cat /opt/ict-trading/.env

# Verify tokens
grep TELEGRAM_BOT_TOKEN /opt/ict-trading/.env
grep TELEGRAM_CHAT_ID /opt/ict-trading/.env
```

### High CPU usage

```bash
# Check for stuck processes
ps aux | grep ict-trading

# Check logs for errors
sudo journalctl -u ict-trading --since "1 hour ago" | grep ERROR
```

### Database issues

```bash
# Check database size
ls -lh /opt/ict-trading/signals.db

# Backup database
cp /opt/ict-trading/signals.db /opt/ict-trading/signals.db.backup

# Reinitialize (WARNING: loses all data)
rm /opt/ict-trading/signals.db
python3 -c "from data.database import init_db; init_db()"
```

### Memory issues

```bash
# Check memory usage
free -h

# Check container memory (if using Docker)
docker stats ict-trading

# Increase swap (if needed)
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## Maintenance

### Weekly Tasks

- [ ] Check dashboard for new signals
- [ ] Review error logs
- [ ] Monitor database size

### Monthly Tasks

- [ ] Retrain ML model: `python3 ml/train_universal_model.py`
- [ ] Back up database
- [ ] Update dependencies

### Quarterly Tasks

- [ ] Review and update ICT rules
- [ ] Performance tuning
- [ ] Security audit

## Support

For issues and questions:
1. Check documentation in `README.md`
2. Review logs: `journalctl -u ict-trading -f`
3. Check `auto_monitor.log` for system events
4. Review `LOYIHA_IMPROVEMENT_PLAN.md` for detailed guide

## Security Notes

1. **Never commit .env file** - It contains sensitive credentials
2. **Use strong passwords** - Minimum 16 characters for ADMIN_PASSWORD
3. **Enable HTTPS** - For webhook mode, use HTTPS with valid certificate
4. **Regular updates** - Keep dependencies updated for security patches
5. **Backup regularly** - Database contains trading history
6. **Rate limiting** - Consider adding rate limiting to dashboard API

---

*Last updated: 2026-08-27*
*Version: 1.0.0*
