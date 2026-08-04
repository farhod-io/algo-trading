"""Liquidity Sweep detection for ICT methodology.

A liquidity sweep occurs when price pushes beyond key levels (recent swing highs/lows,
Equal Highs (EQH), or Equal Lows (EQL)) to trigger stop orders before reversing.

- Bearish Sweep (Buyside Liquidity Sweep): High exceeds a recent swing high.
- Bullish Sweep (Sellside Liquidity Sweep): Low dips below a recent swing low.
"""

from typing import List, Dict
import pandas as pd


def detect_liquidity_sweep(df: pd.DataFrame, swing_window: int = 10) -> List[Dict]:
    """Detect recent liquidity sweeps over rolling swing points.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV dataset containing ['high', 'low', 'close', 'timestamp']
    swing_window : int
        Window size to determine swing highs/lows prior to current candles

    Returns
    -------
    List[Dict]
        List of detected sweeps with keys:
        - type: 'bullish' (sellside sweep) | 'bearish' (buyside sweep)
        - timestamp: time of sweep candle
        - price: extreme price level swept
        - swept_level: original swing level that was swept
    """
    sweeps = []
    if len(df) < swing_window + 2:
        return sweeps

    # Scan the recent 20 candles
    recent_len = min(20, len(df) - swing_window)

    for i in range(len(df) - recent_len, len(df)):
        cur = df.iloc[i]
        prior_slice = df.iloc[max(0, i - swing_window):i]

        prior_high = prior_slice["high"].max()
        prior_low = prior_slice["low"].min()

        # Bearish Liquidity Sweep (Buyside Sweep):
        # Current high exceeds prior swing high, but candle closes back near or below prior high
        if cur["high"] > prior_high:
            sweeps.append({
                "type": "bearish",
                "timestamp": cur["timestamp"],
                "price": float(cur["high"]),
                "swept_level": float(prior_high),
                "rejected": cur["close"] < prior_high
            })

        # Bullish Liquidity Sweep (Sellside Sweep):
        # Current low dips below prior swing low, but candle closes back near or above prior low
        if cur["low"] < prior_low:
            sweeps.append({
                "type": "bullish",
                "timestamp": cur["timestamp"],
                "price": float(cur["low"]),
                "swept_level": float(prior_low),
                "rejected": cur["close"] > prior_low
            })

    return sweeps
