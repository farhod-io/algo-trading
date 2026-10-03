"""Liquidity Sweep detection for ICT methodology.

A liquidity sweep occurs when price pushes beyond key levels (recent swing highs/lows,
Equal Highs (EQH), or Equal Lows (EQL)) to trigger stop orders before reversing.

- Bearish Sweep (Buyside Liquidity Sweep): High exceeds a recent swing high.
- Bullish Sweep (Sellside Liquidity Sweep): Low dips below a recent swing low.
"""

from typing import List, Dict
import pandas as pd


def detect_liquidity_sweep(df: pd.DataFrame, swing_window: int = 10,
                           market_type: str = 'crypto',
                           volume_filter: bool = False) -> List[Dict]:
    """Detect recent liquidity sweeps over rolling swing points.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV dataset containing ['high', 'low', 'close', 'timestamp']
    swing_window : int
        Window size to determine swing highs/lows prior to current candles
    market_type : str
        'crypto' or 'futures'
    volume_filter : bool
        If True, validate that sweep candle has higher volume than average (stop hunt verification)

    Returns
    -------
    List[Dict]
        List of detected sweeps
    """
    sweeps = []
    if len(df) < swing_window + 2:
        return sweeps

    # Scan the recent 20 candles
    recent_len = min(20, len(df) - swing_window)
    has_volume = "volume" in df.columns

    for i in range(len(df) - recent_len, len(df)):
        cur = df.iloc[i]
        prior_slice = df.iloc[max(0, i - swing_window):i]

        prior_high = prior_slice["high"].max()
        prior_low = prior_slice["low"].min()
        
        # Volume check for futures
        vol_surge = True
        if market_type == 'futures' and volume_filter and has_volume and len(prior_slice) > 0:
            avg_vol = prior_slice["volume"].mean()
            if avg_vol > 0:
                vol_surge = cur["volume"] >= (1.5 * avg_vol)

        # Bearish Liquidity Sweep (Buyside Sweep):
        if cur["high"] > prior_high and vol_surge:
            sweeps.append({
                "type": "bearish",
                "timestamp": cur["timestamp"],
                "price": float(cur["high"]),
                "swept_level": float(prior_high),
                "rejected": cur["close"] < prior_high,
                "vol_surge": vol_surge
            })

        # Bullish Liquidity Sweep (Sellside Sweep):
        if cur["low"] < prior_low and vol_surge:
            sweeps.append({
                "type": "bullish",
                "timestamp": cur["timestamp"],
                "price": float(cur["low"]),
                "swept_level": float(prior_low),
                "rejected": cur["close"] > prior_low,
                "vol_surge": vol_surge
            })

    return sweeps


def detect_asian_range_sweep(df: pd.DataFrame) -> Dict:
    """Detect if London or NY session swept the Asian session (05:00 - 10:00 UTC) High or Low."""
    if df is None or len(df) < 10 or "timestamp" not in df.columns:
        return {"has_asian_sweep": False, "sweep_type": None}

    df_copy = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_copy["timestamp"]):
        df_copy["timestamp"] = pd.to_datetime(df_copy["timestamp"], utc=True)

    # Filter Asian session candles (05:00 to 10:00 UTC)
    asian_df = df_copy[(df_copy["timestamp"].dt.hour >= 5) & (df_copy["timestamp"].dt.hour < 10)]
    if asian_df.empty:
        return {"has_asian_sweep": False, "sweep_type": None}

    asian_high = float(asian_df["high"].max())
    asian_low = float(asian_df["low"].min())

    # Latest 5 candles (Post-Asian London/NY session)
    recent_slice = df_copy.tail(5)
    for _, row in recent_slice.iterrows():
        if row["timestamp"].hour >= 10:
            if float(row["high"]) > asian_high and float(row["close"]) < asian_high:
                return {"has_asian_sweep": True, "sweep_type": "bearish", "swept_level": asian_high}
            if float(row["low"]) < asian_low and float(row["close"]) > asian_low:
                return {"has_asian_sweep": True, "sweep_type": "bullish", "swept_level": asian_low}

    return {"has_asian_sweep": False, "sweep_type": None}
