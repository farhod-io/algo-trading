"""Scheduler that periodically runs the market scanner and weekly model retraining.
"""

import logging
from datetime import datetime, timezone

from events.event_bus import event_bus
from data.market_data import fetch_recent_candles, fetch_mtf_candles
from strategy.engine import strategy_engine
from data.database import init_db, get_scanner_state, set_scanner_state
from config import SYMBOLS
from services.error_monitor import notify_admin_error
from services.exchange_service import is_market_open

# In-memory deduplication cache: (symbol, direction) -> last_alerted_candle_timestamp
last_alerted_candle = {}

# Durable fallback key prefix so dedup state survives a process restart.
_DEDUP_KEY_PREFIX = "last_alerted_candle:"


def _load_last_alerted(symbol: str, direction: str):
    """Return the last alerted candle ts, preferring memory then the DB."""
    cache_key = (symbol, direction)
    if cache_key in last_alerted_candle:
        return last_alerted_candle[cache_key]

    stored = get_scanner_state(_DEDUP_KEY_PREFIX + f"{symbol}:{direction}")
    if stored is not None:
        # Warm the in-memory cache so the common path stays in memory.
        last_alerted_candle[cache_key] = stored
    return stored


def _remember_alerted(symbol: str, direction: str, candle_ts: str) -> None:
    """Persist the last alerted candle to memory AND the DB."""
    cache_key = (symbol, direction)
    last_alerted_candle[cache_key] = candle_ts
    set_scanner_state(_DEDUP_KEY_PREFIX + f"{symbol}:{direction}", candle_ts)


def scan_market():
    """Fetch MTF market data, evaluate strategies with HTF alignment, and publish non-duplicate signals."""
    # Skip entirely when US futures are closed: yfinance returns stale candles
    # on weekends, which otherwise produce false signals from the same data.
    if not is_market_open():
        logging.info("Market closed (weekend/session break) -- skipping market scan.")
        return

    try:
        logging.info("Running MTF market scan for NQ, ES, Gold at %s", datetime.now(timezone.utc))
        init_db()

        for symbol in SYMBOLS:
            df_ltf, df_htf = fetch_mtf_candles(symbol=symbol, ltf="5m", htf="15m", limit=200)
            if df_ltf.empty:
                continue

            try:
                from data.data_warehouse import save_indicator_snapshot
                save_indicator_snapshot(df_ltf, symbol)
            except Exception as e:
                logging.error(f"Failed to save snapshot for {symbol}: {e}")

            latest_candle_ts = str(df_ltf.iloc[-1].get("timestamp", ""))

            signals = strategy_engine.run_all(df_ltf, symbol, df_htf=df_htf)
            for signal in signals:
                direction = signal.get("direction", "LONG")

                # Deduplication Check: Prevent sending duplicate alert for the exact same candle
                if _load_last_alerted(symbol, direction) == latest_candle_ts:
                    logging.info(f"Duplicate signal suppressed for {symbol} {direction} at candle {latest_candle_ts}")
                    continue

                _remember_alerted(symbol, direction, latest_candle_ts)
                signal["timestamp"] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
                event_bus.publish("SIGNAL_GENERATED", signal)

    except Exception as exc:
        logging.error("Error during market scan: %s", exc)
        notify_admin_error(exc, context="scan_market")


def run_weekly_retraining():
    """Automated weekly background retraining task every Sunday at 00:00 UTC."""
    try:
        logging.info("Starting automated weekly AI model retraining task...")
        from ml.train_universal_model import train_universal_model
        train_universal_model()
        logging.info("Weekly AI model retraining completed successfully!")
    except Exception as exc:
        logging.error("Weekly model retraining failed: %s", exc)
        notify_admin_error(exc, context="run_weekly_retraining")
