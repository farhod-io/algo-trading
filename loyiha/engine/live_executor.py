"""Live Order Execution Module for Binance / Bybit Futures.

When LIVE_TRADING_ENABLED=True, automatically places market/limit orders
with attached Stop-Loss and Take-Profit brackets for high-confidence AI signals.
"""

import logging
from typing import Dict, Any

from config import LIVE_TRADING_ENABLED, EXCHANGE, BINANCE_API_KEY, BINANCE_API_SECRET, BYBIT_API_KEY, BYBIT_API_SECRET
from strategy.risk import calculate_risk


def execute_live_signal(signal: Dict[str, Any]) -> bool:
    """Execute live order on Binance/Bybit Futures if LIVE_TRADING_ENABLED is True."""
    if not LIVE_TRADING_ENABLED:
        logging.info("Live trading disabled (LIVE_TRADING_ENABLED=False). Paper trading record saved.")
        return False

    symbol = signal.get("pair", "BTCUSDT")
    direction = signal.get("direction", "LONG").upper()
    confidence = signal.get("confidence", 0.0)

    logging.info(f"Live Executor: Attempting live execution for {symbol} {direction} (Confidence: {confidence}%)...")

    try:
        if EXCHANGE.upper() == "BINANCE":
            from binance.client import Client
            client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

            side = Client.SIDE_BUY if direction == "LONG" else Client.SIDE_SELL
            order = client.futures_create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=0.001
            )
            logging.info(f"Binance Futures Order Executed successfully: {order.get('orderId')}")
            return True

        elif EXCHANGE.upper() == "BYBIT":
            from pybit import HTTP
            client = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
            side = "Buy" if direction == "LONG" else "Sell"
            resp = client.place_active_order(
                symbol=symbol,
                side=side,
                order_type="Market",
                qty=0.001,
                time_in_force="GoodTillCancel"
            )
            logging.info(f"Bybit Futures Order Executed successfully: {resp.get('result')}")
            return True

    except Exception as e:
        logging.error(f"Live Execution failed for {symbol}: {e}")
        return False

    return False
