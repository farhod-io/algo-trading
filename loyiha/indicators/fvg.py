"""Fair Value Gap (FVG) detection for ICT methodology.

A Fair Value Gap is an imbalance created across 3 consecutive candles:
- Bullish FVG: High of candle 1 is lower than Low of candle 3 (c1.high < c3.low).
- Bearish FVG: Low of candle 1 is higher than High of candle 3 (c1.low > c3.high).
"""

from typing import List, Dict
import pandas as pd


def detect_fvg(df: pd.DataFrame, min_gap_pct: float = 0.0005) -> List[Dict]:
    """Detect Fair Value Gaps in candles DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV DataFrame
    min_gap_pct : float
        Minimum gap size relative to price (e.g. 0.05%) to filter tiny noise

    Returns
    -------
    List[Dict]
        List of dicts representing detected FVGs:
        - type: 'bullish' | 'bearish'
        - start: timestamp of candle 1
        - end: timestamp of candle 3
        - low: lower bound of gap
        - high: upper bound of gap
        - gap_size: high - low
        - gap_size_pct: gap_size / price
        - distance_to_price: distance from current close to gap mid
        - age: number of candles since gap formed
        - mitigated: bool indicating if price returned and filled gap
    """
    gaps = []
    if len(df) < 3:
        return gaps

    curr_close = float(df.iloc[-1]["close"])
    total_candles = len(df)

    for i in range(total_candles - 2):
        c1, c2, c3 = df.iloc[i], df.iloc[i + 1], df.iloc[i + 2]

        # Bullish FVG: c1.high < c3.low
        if c1["high"] < c3["low"]:
            gap_low = float(c1["high"])
            gap_high = float(c3["low"])
            gap_size = gap_high - gap_low
            gap_mid = (gap_low + gap_high) / 2.0
            gap_pct = gap_size / gap_low if gap_low > 0 else 0.0

            if gap_pct >= min_gap_pct:
                # Check if mitigated by subsequent candles
                subsequent = df.iloc[i + 3:] if i + 3 < total_candles else pd.DataFrame()
                mitigated = not subsequent.empty and (subsequent["low"].min() <= gap_low)

                gaps.append({
                    "type": "bullish",
                    "start": c1["timestamp"],
                    "end": c3["timestamp"],
                    "low": gap_low,
                    "high": gap_high,
                    "gap_size": gap_size,
                    "gap_size_pct": gap_pct,
                    "distance_to_price": abs(curr_close - gap_mid),
                    "age": total_candles - (i + 3),
                    "mitigated": mitigated
                })

        # Bearish FVG: c1.low > c3.high
        elif c1["low"] > c3["high"]:
            gap_low = float(c3["high"])
            gap_high = float(c1["low"])
            gap_size = gap_high - gap_low
            gap_mid = (gap_low + gap_high) / 2.0
            gap_pct = gap_size / gap_low if gap_low > 0 else 0.0

            if gap_pct >= min_gap_pct:
                subsequent = df.iloc[i + 3:] if i + 3 < total_candles else pd.DataFrame()
                mitigated = not subsequent.empty and (subsequent["high"].max() >= gap_high)

                gaps.append({
                    "type": "bearish",
                    "start": c1["timestamp"],
                    "end": c3["timestamp"],
                    "low": gap_low,
                    "high": gap_high,
                    "gap_size": gap_size,
                    "gap_size_pct": gap_pct,
                    "distance_to_price": abs(curr_close - gap_mid),
                    "age": total_candles - (i + 3),
                    "mitigated": mitigated
                })

    return gaps
