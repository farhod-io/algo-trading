"""Fibonacci Optimal Trade Entry (OTE) zone calculation.

ICT OTE Zone: Retracement range between 0.618, 0.705, and 0.786 levels.
"""

from typing import Tuple, Dict, Any
import pandas as pd


def calculate_ote_zone(df: pd.DataFrame, window: int = 20) -> Tuple[float, float, float]:
    """Calculate OTE levels (fib_0_618, fib_0_705, fib_0_786) for recent swing.

    Returns
    -------
    Tuple[float, float, float]
        (fib_0_618, fib_0_705, fib_0_786)
    """
    if df.empty:
        raise ValueError("DataFrame is empty")

    recent = df.tail(window)
    swing_high = float(recent["high"].max())
    swing_low = float(recent["low"].min())

    diff = swing_high - swing_low
    if diff == 0:
        return swing_low, swing_low, swing_low

    fib_0_618 = swing_low + diff * 0.618
    fib_0_705 = swing_low + diff * 0.705
    fib_0_786 = swing_low + diff * 0.786

    return fib_0_618, fib_0_705, fib_0_786


def is_price_in_ote(price: float, ote_levels: Tuple[float, float, float]) -> bool:
    """Check if given price is within the 0.618 - 0.786 OTE zone."""
    fib_618, _, fib_786 = ote_levels
    lower = min(fib_618, fib_786)
    upper = max(fib_618, fib_786)
    return lower <= price <= upper
