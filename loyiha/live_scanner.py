"""Live Paper Trading Scanner for ICT-ML Futures Strategy.

Periodically fetches real-time OHLCV data for NQ [1H], CL [15M], GC [15M],
evaluates the combo_fixed strategy, and sends Telegram alerts for valid signals.

Schedule: Configurable (default every 15 minutes)
"""

import os
import sys
import time
import logging
import schedule
import pandas as pd
from datetime import datetime, timezone
from collections import OrderedDict
from typing import Dict, Any, Optional

# Ensure loyiha package is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SCAN_INTERVAL_MINUTES, ML_CONFIDENCE_THRESHOLD
from data.market_data import fetch_mtf_candles
from strategy.combo_fixed import evaluate_ict_combo_fixed, is_valid_signal_for_asset
from ml.predict import predict_signal_confidence, get_model_version
from ml.features import extract_features
from services.exchange_service import is_market_open

# ── Logging Configuration ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("live_scanner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("LiveScanner")

# ── Asset Configurations ──
# Based on the locked backtest results: NQ [1H], CL [15M], GC [15M]
ASSETS = {
    "NQ": {"ltf": "1h", "htf": "4h"},
    "CL": {"ltf": "15m", "htf": "4h"},
    "GC": {"ltf": "15m", "htf": "4h"}
}

# Deduplication cache: (symbol, direction, current_candle_timestamp)
# Bounded OrderedDict to prevent unbounded memory growth in long-running processes
_processed_signals: OrderedDict[str, None] = OrderedDict()
_MAX_PROCESSED_SIGNALS = 2000


def send_telegram_message(text: str):
    """Dispatch signal message to Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not found. Skipping notification.")
        return

    import asyncio
    from telegram import Bot

    async def _send():
        try:
            bot = Bot(token=TELEGRAM_BOT_TOKEN)
            async with bot:
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Telegram API Error: {e}")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send())
    except RuntimeError:
        asyncio.run(_send())


def generate_tv_link(symbol: str, tf: str) -> str:
    """Generate TradingView link for the asset."""
    tv_symbols = {"NQ": "CME_MINI:NQ1!", "CL": "NYMEX:CL1!", "GC": "COMEX:GC1!"}
    tv_intervals = {"15m": "15", "1h": "60", "4h": "240"}
    sym = tv_symbols.get(symbol, symbol)
    interval = tv_intervals.get(tf, tf.replace("m", "").replace("h", ""))
    return f"https://www.tradingview.com/chart/?symbol={sym}&interval={interval}"


def format_signal(symbol: str, tf: str, data: Dict[str, Any]) -> str:
    """Format the signal message per user requirements."""
    d = data['direction']
    icon = "📈" if d == "LONG" else "📉"
    return (
        f"🚨 *YANGI SIGNAL: {symbol} {tf.upper()}*\n"
        f"{icon} Yo'nalish: *{d}*\n"
        f"🎯 Kirish narxi: *{data['entry']:.2f}*\n"
        f"🛑 Stop Loss: *{data['sl']:.2f}* (Risk: 0.5%)\n"
        f"💰 Target: *{data['tp1']:.2f}, {data['tp2']:.2f}*\n"
        f"🧠 ML Confidence: *{data['confidence']:.1f}%*\n"
        f"📊 Sabab: {' + '.join(data['reasons'])}\n"
        f"📉 Chart: [TradingView Link]({generate_tv_link(symbol, tf)})"
    )


def process_asset(symbol: str, config: Dict[str, str]):
    """Main logic to fetch, evaluate, and alert for a single asset."""
    try:
        ltf, htf = config["ltf"], config["htf"]
        
        # 1. Fetch Data
        df_ltf, df_htf = fetch_mtf_candles(symbol=symbol, ltf=ltf, htf=htf, limit=200)
        if df_ltf.empty or len(df_ltf) < 20:
            return

        # 2. Evaluate Strategy
        result = evaluate_ict_combo_fixed(
            df=df_ltf, df_htf=df_htf, market_type='futures',
            require_killzone=True, strict_htf_alignment=True,
            symbol=symbol, timeframe=ltf
        )
        
        direction = result.get("direction", "NEUTRAL")
        if direction == "NEUTRAL":
            return

        # 3. Extra Validation (Asset specific + H4 EMA)
        validation = is_valid_signal_for_asset(
            symbol=symbol, timeframe=ltf, direction=direction,
            df_h4=df_htf, df_ltf=df_ltf
        )
        if not validation.get("is_valid"):
            return

        # 4. Calculate Targets (ATR-based)
        last_price = float(df_ltf['close'].iloc[-1])
        atr = float(df_ltf['high'].sub(df_ltf['low']).rolling(14).mean().iloc[-1])
        
        sl_dist = atr * 1.2
        tp1_dist = atr * 2.0
        tp2_dist = atr * 3.5

        if direction == "LONG":
            entry, sl, tp1, tp2 = last_price, last_price - sl_dist, last_price + tp1_dist, last_price + tp2_dist
        else:
            entry, sl, tp1, tp2 = last_price, last_price + sl_dist, last_price - tp1_dist, last_price - tp2_dist

        # 5. ML Confidence Score
        details = result.get("details", {})
        features = extract_features(df_ltf, details)
        rule_conf = result.get("confluence_score", 0.8)
        ml_conf = predict_signal_confidence(features, rule_confidence=rule_conf) * 100

        # 5b. Confidence Threshold Filter
        if ml_conf < ML_CONFIDENCE_THRESHOLD * 100:
            logger.info(
                "⏭️ FILTERED: %s %s — Confidence %.1f%% < Threshold %.1f%%",
                symbol, direction, ml_conf, ML_CONFIDENCE_THRESHOLD * 100
            )
            return

        # 6. Deduplication
        candle_ts = str(df_ltf['timestamp'].iloc[-1])
        signal_id = f"{symbol}_{direction}_{candle_ts}"
        if signal_id in _processed_signals:
            return
        _processed_signals[signal_id] = None
        while len(_processed_signals) > _MAX_PROCESSED_SIGNALS:
            _processed_signals.popitem(last=False)
        
        # 7. Determine Reasons
        reasons = []
        if validation.get("htf_trend") == direction.upper():
            reasons.append(f"H4 {direction.title()}")
        if details.get("fvgs_near_count", 0) > 0: reasons.append("FVG")
        if details.get("unicorns"): reasons.append("Unicorn")
        if details.get("silver_bullets"): reasons.append("Silver Bullet")
        if details.get("in_ote"): reasons.append("OTE Zone")
        if not reasons: reasons.append("ICT Combo")

        # 8. Send Alert
        payload = {
            "direction": direction,
            "symbol": symbol,
            "entry": entry,
            "entry_price": entry,
            "sl": sl,
            "stop_loss": sl,
            "tp1": tp1,
            "take_profit": tp1,
            "tp2": tp2,
            "confidence": ml_conf,
            "reasons": reasons,
        }
        msg = format_signal(symbol, ltf, payload)
        send_telegram_message(msg)
        
        logger.info(f"✅ SIGNAL: {symbol} {direction} @ {entry:.2f} | Confidence: {ml_conf:.1f}%")
        return payload

    except Exception as e:
        logger.error(f"❌ Error processing {symbol}: {e}", exc_info=True)
        return None


def scan_market():
    """Scheduled job entry point."""
    if not is_market_open():
        logger.info("Market is closed. Skipping scan cycle.")
        return

    logger.info("--- Starting Market Scan Cycle ---")
    for sym, cfg in ASSETS.items():
        process_asset(sym, cfg)
    logger.info("--- Scan Cycle Finished ---")


if __name__ == "__main__":
    logger.info("🚀 Live Paper Trading Scanner Initialized.")
    logger.info(f"⏰ Scanning interval: {SCAN_INTERVAL_MINUTES} minutes")
    
    # Run once immediately on start
    scan_market()
    
    # Schedule subsequent runs
    schedule.every(SCAN_INTERVAL_MINUTES).minutes.do(scan_market)

    while True:
        schedule.run_pending()
        time.sleep(1)
