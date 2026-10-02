FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY loyiha/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY loyiha/ ./

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Create necessary directories
RUN mkdir -p /app/data /app/dashboard/templates

# Expose ports
EXPOSE 5000 8443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "from data.database import init_db; init_db(); print('OK')" || exit 1

# Environment variables (override these in production)
ENV TELEGRAM_BOT_TOKEN=""
ENV TELEGRAM_CHAT_ID=""
ENV DATABASE_URL="sqlite:///./signals.db"
ENV ML_CONFIDENCE_THRESHOLD="0.80"
ENV SCAN_INTERVAL_MINUTES="15"
ENV EXCHANGE="BINANCE"

# Default command - run the bot
CMD ["python3", "main.py"]
