import os
import warnings
from dotenv import load_dotenv

# Suppress urllib3 NotOpenSSLWarning on macOS LibreSSL and asyncio ResourceWarnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
warnings.filterwarnings("ignore", message=".*LibreSSL.*")
warnings.filterwarnings("ignore", category=ResourceWarning)

_loyiha_dir = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_loyiha_dir, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path, override=True)
else:
    load_dotenv(override=True)

# --- API Configuration ---
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

# --- Market Data Configuration ---
SYMBOL = "NQ"  # Primary Futures Pair: NQ (Nasdaq-100 Futures)
SYMBOLS = ["NQ", "ES", "GC"]  # Supported Pairs: NQ (Nasdaq), ES (S&P 500), GC (Gold)
TIMEFRAME = "15m"    # Candlestick timeframe for scanning (15-minute timeframe)
SCAN_INTERVAL_MINUTES = 15  # How often to scan the market (every 15 minutes)

# Choose one of the exchanges / platforms
EXCHANGE = "BINANCE"  # or "BYBIT"
LEVERAGE = 10.0      # Default futures credit leverage
INITIAL_BALANCE = 50000.0  # Default Prop Firm Balance ($50,000)
DEFAULT_RISK_PCT = 0.5     # Default Risk per trade (0.5% = $250 max loss)

# Live Trading Execution Safety Toggle (False by default)
LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"

# Validate required API keys only if live execution is explicitly enabled
if LIVE_TRADING_ENABLED:
    if EXCHANGE == "BINANCE":
        if not BINANCE_API_KEY or not BINANCE_API_SECRET:
            raise ValueError("BINANCE_API_KEY and BINANCE_API_SECRET must be set in .env file when LIVE_TRADING_ENABLED is true!")
    elif EXCHANGE == "BYBIT":
        if not BYBIT_API_KEY or not BYBIT_API_SECRET:
            raise ValueError("BYBIT_API_KEY and BYBIT_API_SECRET must be set in .env file when LIVE_TRADING_ENABLED is true!")

# --- Telegram Bot Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip("'\"")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip("'\"")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", TELEGRAM_CHAT_ID)


def validate_telegram_config():
    """Verify that Telegram credentials are configured before starting the bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set in .env file!")
    if not TELEGRAM_CHAT_ID:
        raise ValueError("TELEGRAM_CHAT_ID must be set in .env file!")

# Webhook vs Polling Configuration (for Production VPS deployment)
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))
WEBHOOK_LISTEN = os.getenv("WEBHOOK_LISTEN", "0.0.0.0")

# --- ICT Model Specific Configurations ---
# Silver Bullet killzones in UTC (rule.md defines them in EST = UTC-5):
#   London 03:00-04:00 EST -> 08:00-09:00 UTC
#   NY AM  10:00-11:00 EST -> 15:00-16:00 UTC
#   NY PM  14:00-15:00 EST -> 19:00-20:00 UTC
# indicators/silver_bullet.py reads this list, so windows are tunable here.
SILVER_BULLET_TIMES = [
    {"start": "08:00", "end": "09:00"},
    {"start": "15:00", "end": "16:00"},
    {"start": "19:00", "end": "20:00"},
]

# --- ML Model Configuration ---
ML_CONFIDENCE_THRESHOLD = 0.80  # Only show signals with high confidence > 80%
MODEL_PATH = "ml_model.json"   # Path to save/load XGBoost model

# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./signals.db")

# --- Dynamic Configurations Override ---
import json
CONFIG_LOCAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_local.json")
if os.path.exists(CONFIG_LOCAL_PATH):
    try:
        with open(CONFIG_LOCAL_PATH, "r") as f:
            _local_config = json.load(f)
            if "symbols" in _local_config:
                SYMBOLS = _local_config["symbols"]
                if SYMBOLS:
                    SYMBOL = SYMBOLS[0]
            if "timeframe" in _local_config:
                TIMEFRAME = _local_config["timeframe"]
            if "ml_confidence_threshold" in _local_config:
                ML_CONFIDENCE_THRESHOLD = float(_local_config["ml_confidence_threshold"])
            if "scan_interval_minutes" in _local_config:
                SCAN_INTERVAL_MINUTES = int(_local_config["scan_interval_minutes"])
            if "leverage" in _local_config:
                LEVERAGE = float(_local_config["leverage"])
            if "initial_balance" in _local_config:
                INITIAL_BALANCE = float(_local_config["initial_balance"])
    except Exception as e:
        import logging
        logging.warning("Failed to load config_local.json: %s", e)
