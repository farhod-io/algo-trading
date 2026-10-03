#!/bin/bash

# ICT-ML Trading System - Health Check Script

set -e

echo "=================================================="
echo "ICT-ML Trading System - Health Check"
echo "=================================================="
echo "Started at: $(date)"
echo ""

# Configuration
PROJECT_DIR="/opt/ict-trading"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check 1: Is service running?
echo -e "${GREEN}[1/5] Checking service status...${NC}"
if systemctl is-active --quiet ict-trading; then
    echo -e "${GREEN}✅ Service is running${NC}"
else
    echo -e "${RED}❌ Service is not running${NC}"
    exit 1
fi

# Check 2: Database
echo -e "${GREEN}[2/5] Checking database...${NC}"
if [ -f "$PROJECT_DIR/signals.db" ]; then
    DB_SIZE=$(stat -f%z "$PROJECT_DIR/signals.db" 2>/dev/null || stat -c%s "$PROJECT_DIR/signals.db" 2>/dev/null)
    echo -e "${GREEN}✅ Database exists ($DB_SIZE bytes)${NC}"
else
    echo -e "${RED}❌ Database not found${NC}"
    exit 1
fi

# Check 3: ML Model
echo -e "${GREEN}[3/5] Checking ML model...${NC}"
if [ -f "$PROJECT_DIR/ml_model.json" ]; then
    MODEL_SIZE=$(stat -f%z "$PROJECT_DIR/ml_model.json" 2>/dev/null || stat -c%s "$PROJECT_DIR/ml_model.json" 2>/dev/null)
    echo -e "${GREEN}✅ ML model exists ($MODEL_SIZE bytes)${NC}"
else
    echo -e "${RED}❌ ML model not found${NC}"
    exit 1
fi

# Check 4: Disk space
echo -e "${GREEN}[4/5] Checking disk space...${NC}"
DISK_USAGE=$(df -h "$PROJECT_DIR" | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_USAGE" -lt 90 ]; then
    echo -e "${GREEN}✅ Disk usage OK (${DISK_USAGE}%)${NC}"
else
    echo -e "${YELLOW}⚠️  High disk usage (${DISK_USAGE}%)${NC}"
fi

# Check 5: Recent logs
echo -e "${GREEN}[5/5] Checking recent logs...${NC}"
if journalctl -u ict-trading --since "1 hour ago" | grep -q "ERROR"; then
    echo -e "${YELLOW}⚠️  Recent errors found in logs${NC}"
    echo "Last 5 error lines:"
    journalctl -u ict-trading --since "1 hour ago" | grep "ERROR" | tail -5
else
    echo -e "${GREEN}✅ No recent errors in logs${NC}"
fi

echo ""
echo "=================================================="
echo -e "${GREEN}Health check completed!${NC}"
echo "=================================================="
