"""Order Block and Breaker Block detection for ICT methodology.

- Order Block (OB): The last opposite-color candle before a strong displacement
  move that breaks market structure (MSS) or leaves an FVG.
- Breaker Block: An Order Block that was subsequently invalidated (broken by price
  close) and now acts as support/resistance in the opposite direction.
"""

from typing import List, Dict
import pandas as pd


def detect_orderblocks(df: pd.DataFrame, window: int = 20) -> List[Dict]:
    """Detect valid Bullish and Bearish Order Blocks.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV candles dataframe with ['open', 'high', 'low', 'close', 'timestamp']
    window : int
        Number of candles to scan for recent OBs

    Returns
    -------
    List[Dict]
        List of dicts representing Order Blocks:
        - type: 'bullish' | 'bearish'
        - start: timestamp of the OB candle
        - low: OB candle low price
        - high: OB candle high price
        - open: OB candle open price
        - close: OB candle close price
    """
    obs = []
    if len(df) < 5:
        return obs

    subset = df.tail(window)
    n = len(subset)

    for i in range(1, n - 2):
        c_prev = subset.iloc[i - 1]
        c_ob = subset.iloc[i]
        c_next1 = subset.iloc[i + 1]
        c_next2 = subset.iloc[i + 2]

        # Bullish Order Block:
        # Last bearish candle (close < open) followed by strong bullish candles (displacement)
        if c_ob["close"] < c_ob["open"]:
            move_up = (c_next2["close"] - c_ob["low"]) / c_ob["low"] if c_ob["low"] > 0 else 0
            if c_next1["close"] > c_ob["high"] or move_up > 0.003:  # 0.3% displacement
                obs.append({
                    "type": "bullish",
                    "timestamp": c_ob["timestamp"],
                    "low": c_ob["low"],
                    "high": c_ob["high"],
                    "open": c_ob["open"],
                    "close": c_ob["close"]
                })

        # Bearish Order Block:
        # Last bullish candle (close > open) followed by strong bearish candles (displacement)
        elif c_ob["close"] > c_ob["open"]:
            move_down = (c_ob["high"] - c_next2["close"]) / c_ob["high"] if c_ob["high"] > 0 else 0
            if c_next1["close"] < c_ob["low"] or move_down > 0.003:  # 0.3% displacement
                obs.append({
                    "type": "bearish",
                    "timestamp": c_ob["timestamp"],
                    "low": c_ob["low"],
                    "high": c_ob["high"],
                    "open": c_ob["open"],
                    "close": c_ob["close"]
                })

    return obs


def detect_breaker_blocks(df: pd.DataFrame, window: int = 30) -> List[Dict]:
    """Detect Breaker Blocks (invalidated Order Blocks that invert role).

    Returns
    -------
    List[Dict]
        - type: 'bullish' (previously bearish OB broken upwards)
                'bearish' (previously bullish OB broken downwards)
        - low, high, timestamp
    """
    obs = detect_orderblocks(df, window=window)
    breakers = []
    if not obs:
        return breakers

    last_close = df.iloc[-1]["close"]

    for ob in obs:
        if ob["type"] == "bullish" and last_close < ob["low"]:
            breakers.append({
                "type": "bearish",  # Now acts as bearish resistance
                "timestamp": ob["timestamp"],
                "low": ob["low"],
                "high": ob["high"]
            })
        elif ob["type"] == "bearish" and last_close > ob["high"]:
            breakers.append({
                "type": "bullish",  # Now acts as bullish support
                "timestamp": ob["timestamp"],
                "low": ob["low"],
                "high": ob["high"]
            })

    return breakers
