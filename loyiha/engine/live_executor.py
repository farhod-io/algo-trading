"""Live order execution entry point.

This used to contain a second, independent implementation that placed a market
order with a hardcoded ``quantity=0.001`` and no Stop-Loss / Take-Profit
brackets. It now delegates to ``services.order_execution_service`` so there is a
single source of truth for order placement.

Execution is gated twice: ``LIVE_TRADING_ENABLED`` must be true in ``.env``,
otherwise nothing is sent to the exchange. Note that no code in the signal path
calls this module any more -- ``rule.md`` requires the system to signal only.
"""

import logging
from typing import Dict, Any

from services.order_execution_service import live_order_executor
from strategy.risk import calculate_risk


def execute_live_signal(signal: Dict[str, Any]) -> bool:
    """Execute a live order for `signal` through the shared execution service.

    Returns True only when the exchange reported a filled order.
    """
    if not live_order_executor.enabled:
        logging.info("Live trading disabled (LIVE_TRADING_ENABLED=False). No order placed.")
        return False

    symbol = signal.get("pair", "")
    direction = signal.get("direction", "LONG").upper()
    entry_price = float(signal.get("entry_price", 0.0) or 0.0)

    # Derive real SL/TP instead of the old hardcoded quantity order.
    if entry_price > 0:
        sl, tp1, _tp2 = calculate_risk(entry_price=entry_price, direction=direction)
    else:
        sl = float(signal.get("stop_loss", 0.0) or 0.0)
        tp1 = float(signal.get("take_profit_1", signal.get("take_profit", 0.0)) or 0.0)

    quantity = float(signal.get("position_size", 0.0) or 0.0)
    if quantity <= 0:
        logging.warning(
            "Live Executor: no position_size on signal for %s; refusing to guess a quantity.",
            symbol,
        )
        return False

    result = live_order_executor.execute_live_order(
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        stop_loss=sl,
        take_profit=tp1,
        quantity=quantity,
    )
    return result is not None
