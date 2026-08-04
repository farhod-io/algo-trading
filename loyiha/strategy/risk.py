"""Risk calculation utilities for ICT signals.

Provides dynamic ATR (Average True Range) and Swing High / Low stop loss calculations,
as well as fixed fallback percentage risk math for target Risk:Reward Ratios.
"""

from typing import Tuple, Optional
import pandas as pd
from ml.features import calculate_atr

DEFAULT_RRR1 = 1.85  # TP1 Risk:Reward ratio
DEFAULT_RRR2 = 3.70  # TP2 Risk:Reward ratio


def calculate_risk(
    entry_price: float,
    direction: str,
    sl_percent: float = 0.35,
    df: Optional[pd.DataFrame] = None,
    atr_mult: float = 1.5,
    swing_high: Optional[float] = None,
    swing_low: Optional[float] = None
) -> Tuple[float, float, float]:
    """Calculate Stop-Loss, Take-Profit 1, and Take-Profit 2 prices dynamically.

    If df is provided, uses ATR and Swing High/Low levels to compute dynamic SL distance.
    Otherwise, uses percentage distance sl_percent.
    """
    if entry_price <= 0:
        raise ValueError("entry_price must be greater than 0")

    norm_dir = direction.strip().upper()

    # Dynamic ATR and Swing Level Risk Math
    sl_distance = None
    if df is not None and not df.empty and len(df) >= 14:
        try:
            latest_atr = float(calculate_atr(df, period=14))
            if latest_atr > 0:
                atr_distance = latest_atr * atr_mult
                if norm_dir == "LONG" and swing_low and swing_low < entry_price:
                    swing_distance = (entry_price - swing_low) * 1.1
                    sl_distance = max(atr_distance, swing_distance)
                elif norm_dir == "SHORT" and swing_high and swing_high > entry_price:
                    swing_distance = (swing_high - entry_price) * 1.1
                    sl_distance = max(atr_distance, swing_distance)
                else:
                    sl_distance = atr_distance
        except Exception:
            sl_distance = None

    # Fallback to percentage distance if ATR / Swing is not available
    if sl_distance is None or sl_distance <= 0:
        sl_distance = entry_price * (sl_percent / 100.0)

    # Bound SL distance between 0.15% min and 1.5% max of entry price
    min_dist = entry_price * 0.0015
    max_dist = entry_price * 0.0150
    sl_distance = max(min_dist, min(max_dist, sl_distance))

    if norm_dir == "LONG":
        stop_loss = entry_price - sl_distance
        tp1 = entry_price + (sl_distance * DEFAULT_RRR1)
        tp2 = entry_price + (sl_distance * DEFAULT_RRR2)
    elif norm_dir == "SHORT":
        stop_loss = entry_price + sl_distance
        tp1 = entry_price - (sl_distance * DEFAULT_RRR1)
        tp2 = entry_price - (sl_distance * DEFAULT_RRR2)
    else:
        raise ValueError(f"Invalid direction: '{direction}'. Expected 'LONG' or 'SHORT'.")

    return round(stop_loss, 2), round(tp1, 2), round(tp2, 2)
