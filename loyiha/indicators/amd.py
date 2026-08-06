"""Power of 3 (AMD: Accumulation, Manipulation, Distribution) model for ICT.

1. Accumulation: Range-bound Asian session (00:00 - 06:00 UTC) establishing high/low bounds.
2. Manipulation: Fake breakout / liquidity sweep during London Open (07:00 - 10:00 UTC).
3. Distribution: True trend expansion into NY Session (12:00 - 17:00 UTC).
"""

from datetime import time
from typing import List, Dict, Optional
import pandas as pd
from .liquidity import detect_liquidity_sweep

ASIAN_START = time(0, 0)
ASIAN_END = time(6, 0)

LONDON_MANIP_START = time(7, 0)
LONDON_MANIP_END = time(10, 0)

NY_DIST_START = time(12, 0)
NY_DIST_END = time(17, 0)


def detect_amd(df: pd.DataFrame) -> Optional[Dict]:
    """Detect Power of 3 (AMD) phase and current setup.

    Returns
    -------
    Optional[Dict]
        - asian_high, asian_low
        - manipulation_detected: bool
        - manipulation_type: 'bullish' (swept asian low) | 'bearish' (swept asian high)
        - current_phase: 'Accumulation' | 'Manipulation' | 'Distribution' | 'None'
    """
    if df.empty or "timestamp" not in df.columns:
        return None

    # Get today's candles
    last_ts = pd.to_datetime(df.iloc[-1]["timestamp"])
    today_mask = pd.to_datetime(df["timestamp"]).dt.date == last_ts.date()
    today_df = df[today_mask].copy()

    if today_df.empty:
        return None

    # 1. Asian Accumulation Range
    asian_candles = today_df[
        today_df["timestamp"].dt.time.apply(lambda t: ASIAN_START <= t <= ASIAN_END)
    ]

    if asian_candles.empty:
        return None

    asian_high = float(asian_candles["high"].max())
    asian_low = float(asian_candles["low"].min())

    # 2. London Manipulation Phase Check
    current_time = last_ts.time()
    current_phase = "None"
    if ASIAN_START <= current_time <= ASIAN_END:
        current_phase = "Accumulation"
    elif LONDON_MANIP_START <= current_time <= LONDON_MANIP_END:
        current_phase = "Manipulation"
    elif NY_DIST_START <= current_time <= NY_DIST_END:
        current_phase = "Distribution"

    # Check for sweeps of Asian High/Low during London session
    london_candles = today_df[
        today_df["timestamp"].dt.time.apply(lambda t: LONDON_MANIP_START <= t <= LONDON_MANIP_END)
    ]

    manipulation_detected = False
    manipulation_type = None

    if not london_candles.empty:
        max_london_high = float(london_candles["high"].max())
        min_london_low = float(london_candles["low"].min())

        if max_london_high > asian_high:
            manipulation_detected = True
            manipulation_type = "bearish"  # Swept Asian High (buyside sweep) -> expect bearish distribution
        elif min_london_low < asian_low:
            manipulation_detected = True
            manipulation_type = "bullish"  # Swept Asian Low (sellside sweep) -> expect bullish distribution

    return {
        "asian_high": asian_high,
        "asian_low": asian_low,
        "current_phase": current_phase,
        "manipulation_detected": manipulation_detected,
        "manipulation_type": manipulation_type
    }
