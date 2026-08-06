"""Market Structure Shift (MSS) detection for ICT methodology.

An MSS occurs when price closes beyond a established swing high (Bullish MSS)
or swing low (Bearish MSS), signalling a structural shift in trend direction.
"""

from typing import List, Dict
import pandas as pd


def detect_mss(df: pd.DataFrame, swing_lookback: int = 15) -> List[Dict]:
    """Detect Market Structure Shifts.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV dataset
    swing_lookback : int
        Lookback window to define swing high and swing low

    Returns
    -------
    List[Dict]
        List of dicts:
        - type: 'bullish' | 'bearish'
        - timestamp: timestamp of breaking candle
        - price: closing price of breaking candle
        - broken_level: price of swing high/low broken
    """
    shifts = []
    if len(df) < swing_lookback + 2:
        return shifts

    # Scan last 20 candles
    recent_count = min(20, len(df) - swing_lookback)

    for i in range(len(df) - recent_count, len(df)):
        cur = df.iloc[i]
        prior_slice = df.iloc[max(0, i - swing_lookback):i]

        swing_high = prior_slice["high"].max()
        swing_low = prior_slice["low"].min()

        # Bullish MSS: close above prior swing high
        if cur["close"] > swing_high:
            shifts.append({
                "type": "bullish",
                "timestamp": cur["timestamp"],
                "price": float(cur["close"]),
                "broken_level": float(swing_high)
            })

        # Bearish MSS: close below prior swing low
        elif cur["close"] < swing_low:
            shifts.append({
                "type": "bearish",
                "timestamp": cur["timestamp"],
                "price": float(cur["close"]),
                "broken_level": float(swing_low)
            })

    return shifts
