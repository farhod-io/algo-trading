import os
import warnings
from dotenv import load_dotenv

# Suppress urllib3 NotOpenSSLWarning on macOS LibreSSL and asyncio ResourceWarnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
warnings.filterwarnings("ignore", message=".*LibreSSL.*")
warnings.filterwarnings("ignore", category=ResourceWarning)

load_dotenv(override=True)

# --- API Configuration ---
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

# Choose one of the exchanges / platforms
EXCHANGE = "BINANCE"  # or "BYBIT"
LEVERAGE = 10.0      # Default futures credit leverage
INITIAL_BALANCE = 50000.0  # Default Prop Firm Balance ($50,000)
DEFAULT_RISK_PCT = 0.5     # Default Risk per trade (0.5% = $250 max loss)

# Live Trading Execution Safety Toggle (False by default)
LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"

# --- Telegram Bot Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip("'\"")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip("'\"")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", TELEGRAM_CHAT_ID)

# Webhook vs Polling Configuration (for Production VPS deployment)
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))
WEBHOOK_LISTEN = os.getenv("WEBHOOK_LISTEN", "0.0.0.0")

# --- Market Data Configuration ---
SYMBOL = "NQ"  # Primary Futures Pair: NQ (Nasdaq-100 Futures)
SYMBOLS = ["NQ", "ES", "GC"]  # Supported Pairs: NQ (Nasdaq), ES (S&P 500), GC (Gold)
TIMEFRAME = "15m"    # Candlestick timeframe for scanning (15-minute timeframe)
SCAN_INTERVAL_MINUTES = 15  # How often to scan the market (every 15 minutes)

# --- ICT Model Specific Configurations ---
SILVER_BULLET_TIMES = [
    {"start": "07:00", "end": "08:00"},
    {"start": "14:00", "end": "15:00"},
    {"start": "18:00", "end": "19:00"},
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
        pass
