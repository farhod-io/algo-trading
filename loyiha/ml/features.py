"""Feature engineering for the XGBoost model.

Extracts comprehensive price action, indicator, and technical features from candles
and ICT indicator detections.
"""

from typing import Dict, Any
import numpy as np
import pandas as pd


def calculate_rsi(series: pd.Series, period: int = 14) -> float:
    """Calculate RSI for a price series."""
    if len(series) < period + 1:
        return 50.0
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean().iloc[-1]
    avg_loss = loss.rolling(window=period).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate ATR (Average True Range) for OHLC dataframe."""
    if len(df) < period + 1:
        return 0.0
    high_low = df["high"] - df["low"]
    high_prev_close = (df["high"] - df["close"].shift(1)).abs()
    low_prev_close = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return float(tr.rolling(window=period).mean().iloc[-1])


def is_volatility_sufficient(df: pd.DataFrame, period: int = 14, sma_period: int = 50, threshold_multiplier: float = 0.85):
    """Check if current market volatility (ATR) is sufficient compared to historical baseline.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV candle dataframe
    period : int
        ATR lookback period (default: 14)
    sma_period : int
        SMA smoothing period for baseline ATR (default: 50)
    threshold_multiplier : float
        Fraction of average ATR required (default: 0.85 = 85%)

    Returns
    -------
    tuple
        (is_sufficient: bool, current_atr: float, threshold_atr: float)
    """
    if df is None or len(df) < period + 2:
        return True, 0.0, 0.0

    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    high_low = high - low
    high_prev_close = (high - close.shift(1)).abs()
    low_prev_close = (low - close.shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)

    atr_series = tr.rolling(window=period).mean()
    valid_atr = atr_series.dropna()
    if len(valid_atr) == 0:
        return True, 0.0, 0.0

    current_atr = float(atr_series.iloc[-1])
    min_periods = min(len(valid_atr), 10)
    avg_atr_series = atr_series.rolling(window=sma_period, min_periods=min_periods).mean()
    avg_atr = float(avg_atr_series.iloc[-1]) if not avg_atr_series.empty and not pd.isna(avg_atr_series.iloc[-1]) else current_atr

    threshold_atr = avg_atr * threshold_multiplier

    if avg_atr > 0 and current_atr < threshold_atr:
        return False, current_atr, threshold_atr

    return True, current_atr, threshold_atr


def extract_features(df: pd.DataFrame, indicators: Dict[str, Any]) -> pd.DataFrame:
    """Extract flat feature vector from candles and indicator details.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV candles
    indicators : dict
        Dict of indicator results (from combo.py or ICT strategy)
    """
    last = df.iloc[-1]

    # 1. Price Metrics
    close = float(last["close"])
    open_p = float(last["open"])
    high = float(last["high"])
    low = float(last["low"])
    volume = float(last["volume"]) if "volume" in last else 0.0

    total_range = high - low if high != low else 0.0001
    body_size = abs(close - open_p)

    candle_body_ratio = body_size / total_range
    top_wick = (high - max(open_p, close)) / total_range
    bottom_wick = (min(open_p, close) - low) / total_range

    # 2. Rolling Metrics
    close_prices = df["close"].astype(float)

    momentum_5 = (close - close_prices.iloc[-5]) / close_prices.iloc[-5] if len(close_prices) >= 5 else 0.0
    momentum_10 = (close - close_prices.iloc[-10]) / close_prices.iloc[-10] if len(close_prices) >= 10 else 0.0

    returns = close_prices.pct_change()
    volatility_10 = float(returns.tail(10).std()) if len(returns) >= 10 else 0.0

    # 3. Technical Indicators & Feature Engineering Extensions
    rsi_14 = calculate_rsi(close_prices, 14)
    atr_14 = calculate_atr(df, 14)
    atr_ratio = (total_range / atr_14) if atr_14 > 0 else 1.0

    vol_mean_10 = float(df["volume"].astype(float).tail(10).mean()) if "volume" in df and len(df) >= 10 else 1.0
    volume_ratio = volume / vol_mean_10 if vol_mean_10 > 0 else 1.0

    # Trend EMA Features
    ema_9 = float(close_prices.ewm(span=9, adjust=False).mean().iloc[-1])
    ema_21 = float(close_prices.ewm(span=21, adjust=False).mean().iloc[-1])
    trend_ema_diff = (ema_9 - ema_21) / close if close > 0 else 0.0

    # Volume Profile Proxy (POC - Point of Control: price level with highest volume in last 30 candles)
    recent_30 = df.tail(30)
    if "volume" in recent_30 and not recent_30.empty:
        poc_idx = recent_30["volume"].astype(float).idxmax()
        poc_price = float(recent_30.loc[poc_idx, "close"])
        poc_distance = (close - poc_price) / close
    else:
        poc_distance = 0.0

    # Session High/Low Features (Last 24 bars proxy)
    recent_24 = df.tail(24)
    session_high = float(recent_24["high"].max())
    session_low = float(recent_24["low"].min())
    dist_to_session_high = (session_high - close) / close if close > 0 else 0.0
    dist_to_session_low = (close - session_low) / close if close > 0 else 0.0

    # 4. Time & Session Features
    timestamp = pd.to_datetime(last["timestamp"]) if "timestamp" in last else pd.Timestamp.now()
    hour_of_day = timestamp.hour

    # Session classification: 0 = Asian, 1 = London, 2 = NY, 3 = Off-hours
    if 0 <= hour_of_day < 6:
        session_type = 0
    elif 7 <= hour_of_day < 12:
        session_type = 1
    elif 12 <= hour_of_day < 18:
        session_type = 2
    else:
        session_type = 3

    # 5. Indicator Flags & Metrics
    fvgs = indicators.get("fvgs") or indicators.get("fvg") or []
    fvg_detected = int(bool(fvgs))
    fvg_size = float(fvgs[0].get("gap_size", 0.0)) if fvgs and isinstance(fvgs, list) else 0.0
    fvg_distance = float(fvgs[0].get("distance_to_price", 0.0)) if fvgs and isinstance(fvgs, list) else 0.0

    sweeps = indicators.get("sweeps") or indicators.get("liquidity_sweep") or []
    liquidity_sweep = int(bool(sweeps))

    mss_list = indicators.get("mss") or []
    mss_detected = int(bool(mss_list))

    unicorns = indicators.get("unicorns") or indicators.get("unicorn") or []
    unicorn_detected = int(bool(unicorns))

    order_blocks = indicators.get("order_blocks") or []
    orderblock_detected = int(bool(order_blocks))

    silver_bullets = indicators.get("silver_bullets") or []
    silver_bullet_detected = int(bool(silver_bullets))

    ote_tuple = indicators.get("ote", (0.0, 0.0, 0.0))
    ote_low = float(ote_tuple[0] or 0.0)
    ote_mid = float(ote_tuple[1] or 0.0)
    ote_high = float(ote_tuple[2] or 0.0)
    in_ote = int(bool(indicators.get("in_ote", False)))

    features = {
        "fvg_detected": fvg_detected,
        "fvg_size": fvg_size,
        "fvg_distance": fvg_distance,
        "liquidity_sweep": liquidity_sweep,
        "mss_detected": mss_detected,
        "unicorn_detected": unicorn_detected,
        "orderblock_detected": orderblock_detected,
        "silver_bullet_detected": silver_bullet_detected,
        "in_ote": in_ote,
        "ote_low": ote_low,
        "ote_mid": ote_mid,
        "ote_high": ote_high,
        "close_price": close,
        "candle_body_ratio": candle_body_ratio,
        "top_wick_ratio": top_wick,
        "bottom_wick_ratio": bottom_wick,
        "momentum_5": momentum_5,
        "momentum_10": momentum_10,
        "volatility_10": volatility_10,
        "rsi_14": rsi_14,
        "atr_14": atr_14,
        "atr_ratio": atr_ratio,
        "volume_ratio": volume_ratio,
        "trend_ema_diff": trend_ema_diff,
        "poc_distance": poc_distance,
        "dist_to_session_high": dist_to_session_high,
        "dist_to_session_low": dist_to_session_low,
        "hour_of_day": hour_of_day,
        "session_type": session_type
    }

    return pd.DataFrame([features])
