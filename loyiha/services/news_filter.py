"""News event filter and volatility safety checks for ICT strategy.

Prevents signal generation during high-impact news events and extreme volatility spikes.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
import pandas as pd


# Known high-impact news windows (UTC hours) — extend as needed
# Format: (start_hour, end_hour) — signals are suppressed during these windows
NEWS_BLACKOUT_HOURS_UTC = [
    # FOMC announcements (typically 18:00-18:30 UTC)
    (18, 19),
    # NFP / CPI releases (typically 12:30-13:30 UTC)
    (12, 14),
    # Fed Chair press conferences
    (18, 19),
]


def is_news_event_window(timestamp: Optional[pd.Timestamp] = None) -> bool:
    """Check if the given timestamp falls within a known high-impact news blackout window.

    Parameters
    ----------
    timestamp : pd.Timestamp, optional
        Timestamp to check. Defaults to current UTC time.

    Returns
    -------
    bool
        True if current time is inside a news blackout window.
    """
    if timestamp is None:
        timestamp = pd.Timestamp.now(tz="UTC")

    if not isinstance(timestamp, pd.Timestamp):
        timestamp = pd.to_datetime(timestamp)

    # Ensure UTC
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")

    hour = timestamp.hour
    minute = timestamp.minute

    for start_h, end_h in NEWS_BLACKOUT_HOURS_UTC:
        if start_h <= hour < end_h:
            return True

    return False


def is_volatility_spike_unsafe(df: pd.DataFrame, lookback: int = 20, threshold_pct: float = 3.0) -> bool:
    """Detect if the latest candle represents an extreme volatility spike (unsafe for entry).

    A spike is defined as a candle range exceeding `threshold_pct` times the
    average range of the previous `lookback` candles.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV candle dataframe
    lookback : int
        Number of previous candles to compute average range
    threshold_pct : float
        Multiplier of average range to consider as unsafe spike

    Returns
    -------
    bool
        True if the latest candle is an extreme volatility spike.
    """
    if df is None or len(df) < lookback + 1:
        return False

    try:
        recent = df.tail(lookback + 1)
        candle_ranges = (recent["high"].astype(float) - recent["low"].astype(float)).iloc[:-1]
        avg_range = float(candle_ranges.mean())

        if avg_range <= 0:
            return False

        latest_range = float(recent.iloc[-1]["high"]) - float(recent.iloc[-1]["low"])
        return latest_range > (avg_range * threshold_pct)

    except Exception as e:
        logging.warning("News filter volatility check failed: %s", e)
        return False
