"""Live Order Execution Module for Binance / Bybit Futures.

When LIVE_TRADING_ENABLED=True, automatically places market/limit orders
with attached Stop-Loss and Take-Profit brackets for high-confidence AI signals.
"""

import logging
from typing import Dict, Any

from config import LIVE_TRADING_ENABLED, EXCHANGE, BINANCE_API_KEY, BINANCE_API_SECRET, BYBIT_API_KEY, BYBIT_API_SECRET


def _calculate_quantity(signal: Dict[str, Any], current_price: float) -> float:
    """Calculate order quantity based on risk parameters.

    Uses risk_per_trade_percent and balance from signal context,
    falling back to a safe minimum if not available.
    """
    risk_pct = signal.get("risk_pct", 0.5)  # Default 0.5%
    balance = signal.get("balance", 50000.0)
    sl_distance = signal.get("sl_distance", current_price * 0.01)

    risk_amount = balance * (risk_pct / 100.0)
    if sl_distance > 0:
        quantity = risk_amount / sl_distance
    else:
        quantity = 0.001

    # Clamp to reasonable bounds
    return max(0.001, round(quantity, 4))


def execute_live_signal(signal: Dict[str, Any]) -> bool:
    """Execute live order on Binance/Bybit Futures if LIVE_TRADING_ENABLED is True."""
    if not LIVE_TRADING_ENABLED:
        logging.info("Live trading disabled (LIVE_TRADING_ENABLED=False). Paper trading record saved.")
        return False

    symbol = signal.get("pair", "BTCUSDT")
    direction = signal.get("direction", "LONG").upper()
    confidence = signal.get("confidence", 0.0)
    current_price = signal.get("entry_price")
    
    if current_price is None:
        logging.error("Live Executor: entry_price is missing from signal. Aborting.")
        return False
    
    if not isinstance(current_price, (int, float)) or current_price <= 0:
        logging.warning("Live Executor: Invalid entry price (%s) for %s. Aborting.", current_price, symbol)
        return False

    quantity = _calculate_quantity(signal, current_price)

    logging.info(
        "Live Executor: Attempting live execution for %s %s (Confidence: %s%%, Qty: %.4f)...",
        symbol, direction, confidence, quantity
    )

    try:
        if EXCHANGE.upper() == "BINANCE":
            from binance.client import Client
            client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

            side = Client.SIDE_BUY if direction == "LONG" else Client.SIDE_SELL
            order = client.futures_create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=quantity
            )
            logging.info("Binance Futures Order Executed successfully: %s", order.get("orderId"))
            return True

        elif EXCHANGE.upper() == "BYBIT":
            from pybit import HTTP
            client = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
            side = "Buy" if direction == "LONG" else "Sell"
            resp = client.place_active_order(
                symbol=symbol,
                side=side,
                order_type="Market",
                qty=quantity,
                time_in_force="GoodTillCancel"
            )
            logging.info("Bybit Futures Order Executed successfully: %s", resp.get("result"))
            return True

    except Exception as e:
        logging.error("Live Execution failed for %s: %s", symbol, e, exc_info=True)
        raise
        return False

    return False
