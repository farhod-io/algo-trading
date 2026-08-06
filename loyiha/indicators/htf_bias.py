"""HTF (Higher Timeframe) Bias & MMBM / MMSM detection for ICT methodology.

- MMBM (Market Maker Buy Model): HTF trend is bullish, price retests accumulation/discount FVG.
- MMSM (Market Maker Sell Model): HTF trend is bearish, price retests premium FVG.
"""

from typing import Dict, Any
import pandas as pd


def determine_htf_bias(df: pd.DataFrame, window: int = 50) -> Dict[str, Any]:
    """Determine Higher Timeframe (15m/1h) bias from candle dataset.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV candles (preferably 15m or 1h)
    window : int
        Lookback for HTF trend assessment

    Returns
    -------
    Dict[str, Any]
        - bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
        - htf_high: highest price in window
        - htf_low: lowest price in window
        - trend_strength: float
    """
    if df is None or len(df) < 10:
        return {"bias": "NEUTRAL", "htf_high": 0.0, "htf_low": 0.0, "trend_strength": 0.0}

    subset = df.tail(window).copy()
    close_prices = subset["close"].astype(float)
    last_close = float(close_prices.iloc[-1])

    htf_high = float(subset["high"].max())
    htf_low = float(subset["low"].min())

    # EMA 20 vs EMA 50 alignment
    ema_20 = float(close_prices.ewm(span=min(20, len(close_prices)), adjust=False).mean().iloc[-1])
    ema_50 = float(close_prices.ewm(span=min(50, len(close_prices)), adjust=False).mean().iloc[-1])

    first_close = float(close_prices.iloc[0])
    change_pct = (last_close - first_close) / first_close if first_close > 0 else 0.0

    # Determine bias based on EMA crossover + overall price change
    if last_close > ema_20 >= ema_50 or change_pct > 0.003:
        bias = "BULLISH"
    elif last_close < ema_20 <= ema_50 or change_pct < -0.003:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    return {
        "bias": bias,
        "htf_high": htf_high,
        "htf_low": htf_low,
        "trend_strength": round(abs(change_pct) * 100, 2)
    }
