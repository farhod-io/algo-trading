"""ICT Strategy Combination Engine with MARKET TYPE SUPPORT and STRICT HTF/KILLZONE FILTERS.

Supports both crypto and futures markets with adaptive thresholds and strict HTF alignment.
"""

from typing import Dict, Any, Optional, List
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indicators.fvg import detect_fvg
from indicators.liquidity import detect_liquidity_sweep, detect_asian_range_sweep
from indicators.mss import detect_mss
from indicators.orderblock import detect_orderblocks, detect_breaker_blocks
from indicators.fibonacci import calculate_ote_zone, is_price_in_ote
from indicators.unicorn import detect_unicorn
from indicators.amd import detect_amd
from indicators.silver_bullet import detect_silver_bullet
from indicators.htf_bias import determine_htf_bias
from futures.market_config import get_params
from ml.features import is_volatility_sufficient


def is_zone_near_price(zone_low: float, zone_high: float, price: float, 
                       proximity_pct: float = 0.005) -> bool:
    """Check if a zone is near current price (within proximity_pct)."""
    zone_mid = (zone_low + zone_high) / 2.0
    distance = abs(price - zone_mid)
    max_distance = price * proximity_pct
    return distance <= max_distance


def filter_fvgs_by_proximity(fvgs: List[Dict], price: float, 
                             proximity_pct: float = 0.005) -> List[Dict]:
    """Filter FVGs to only include those near current price and not mitigated."""
    filtered = []
    for fvg in fvgs:
        if fvg.get('mitigated', False):
            continue
        if is_zone_near_price(fvg['low'], fvg['high'], price, proximity_pct):
            filtered.append(fvg)
    return filtered


def filter_orderblocks_by_proximity(obs: List[Dict], price: float,
                                   proximity_pct: float = 0.005) -> List[Dict]:
    """Filter Order Blocks to only include those near current price."""
    filtered = []
    for ob in obs:
        if is_zone_near_price(ob['low'], ob['high'], price, proximity_pct):
            filtered.append(ob)
    return filtered


def is_in_trading_killzone(timestamp: pd.Timestamp, dst_offset: int = 0, use_ny_tz: bool = True) -> bool:
    """Check if timestamp falls into London (02-05 NY / 07-11 UTC) or NY (07-12, 13-16 NY / 13-17 UTC) Killzones.
    
    Parameters
    ----------
    timestamp : pd.Timestamp
        Timestamp to check (tz-aware or tz-naive UTC).
    dst_offset : int, default=0
        Manual offset if using fixed UTC hours.
    use_ny_tz : bool, default=True
        Automatically convert to 'America/New_York' timezone for DST resilience.
    """
    if not isinstance(timestamp, pd.Timestamp):
        timestamp = pd.to_datetime(timestamp)

    if use_ny_tz:
        try:
            # Convert to America/New_York timezone for canonical ICT hours
            if timestamp.tzinfo is None:
                ts_ny = timestamp.tz_localize("UTC").tz_convert("America/New_York")
            else:
                ts_ny = timestamp.tz_convert("America/New_York")
            ny_hour = ts_ny.hour
            # London Session: 02:00 - 05:00 NY Time
            is_london_ny = 2 <= ny_hour <= 5
            # NY AM & PM Sessions: 07:00 - 12:00 and 13:00 - 16:00 NY Time
            is_ny_session = (7 <= ny_hour <= 12) or (13 <= ny_hour <= 16)
            if is_london_ny or is_ny_session:
                return True
        except Exception:
            pass

    # Fallback / standard UTC check
    hour = timestamp.hour
    is_london = (7 - dst_offset) <= hour <= (10 - dst_offset)
    is_ny = (13 - dst_offset) <= hour <= (17 - dst_offset)
    return is_london or is_ny


# ==============================================================================
# ASSET SPECIFIC TIMEFRAME CONFIGURATION & BLACKLIST
# ==============================================================================
ASSET_CONFIG = {
    # 1. NQ (Nasdaq 100): Faqat H1 (1H / 60) ruxsat. M15 dagi shovqin va false wicks olib tashlandi.
    "NQ": {
        "allowed_tfs": ["1h", "h1", "60", "60m", "4h", "1d"],
        "description": "Nasdaq 100",
        "comment": "NQ faqat H1 (1H/60) da barqaror; M15 dagi shovqin va false wicks olib tashlandi"
    },
    # 2. ES (S&P 500): Faqat H1 (1H / 60) ruxsat. Micro timeframelar taqiqlangan.
    "ES": {
        "allowed_tfs": ["1h", "h1", "60", "60m", "4h", "1d"],
        "description": "S&P 500",
        "comment": "ES faqat H1 (1H/60) da kuchli confluence beradi; micro timeframelar taqiqlangan"
    },
    # 3. CL (Crude Oil): Ham H1 (1H/60), ham M15 (15m/15) ruxsat. Yuqori likvidlik va kuchli momentum.
    "CL": {
        "allowed_tfs": ["1h", "h1", "60", "60m", "15m", "m15", "15", "4h", "1d"],
        "description": "Crude Oil",
        "comment": "CL ham H1, ham M15 da yuqori likvidlik va kuchli trend momentumiga ega"
    },
    # 4. GC (Gold Futures): FAQAT M15 (15m/15) ruxsat! 1H butunlay o'chirildi (false wicks va stop-hunt ko'p).
    "GC": {
        "allowed_tfs": ["15m", "m15", "15", "4h", "1d"],
        "description": "Gold Futures",
        "comment": "GC 1H da false wicks va stop-hunt ko'p (-$17.6k yo'qotish bo'lgan), 15M da toza ishlaydi (PF 1.73, 44.4% WR)"
    },
    # 5. YM (Dow Jones): Vaqtincha blacklist (allowed_tfs = []). Past RR va sust impuls tufayli to'xtatildi.
    "YM": {
        "allowed_tfs": [],
        "description": "Dow Jones",
        "comment": "YM vaqtincha blacklist: past RR va sust impuls tufayli savdo to'xtatildi"
    },
    # 6. SI (Silver): Vaqtincha blacklist (allowed_tfs = []). Yuqori spred va salbiy PnL tufayli to'xtatildi.
    "SI": {
        "allowed_tfs": [],
        "description": "Silver",
        "comment": "SI vaqtincha blacklist: yuqori spred va salbiy PnL tufayli to'xtatildi"
    },
    # 7. RTY (Russell 2000): Butunlay blacklist (allowed_tfs = []). Foydalanuvchi talabiga ko'ra o'chirildi.
    "RTY": {
        "allowed_tfs": [],
        "description": "Russell 2000",
        "comment": "RTY butunlay blacklist: foydalanuvchi talabiga ko'ra o'chirildi"
    },
}


def is_valid_signal_for_asset(symbol: str = "NQ",
                              timeframe: str = "1h",
                              direction: str = "NEUTRAL",
                              df_h4: Optional[pd.DataFrame] = None,
                              df_ltf: Optional[pd.DataFrame] = None,
                              min_spread_pct: float = 0.0003) -> Dict[str, Any]:
    """Validate signal based on Asset-Specific Timeframe Permissions and H4 EMA 21/50 Trend & Choppiness Filter.

    Rules:
    ------
    1. Asset Timeframe Restrictions (via ASSET_CONFIG):
       - NQ, ES: Only H1 (1H / 60)
       - CL: H1 and M15 (15m / M15 / 15)
       - GC: ONLY M15 (15m / M15 / 15) (H1 is strictly prohibited)
       - YM, SI, RTY: Blacklisted (allowed_tfs = [])
    2. H4 EMA 21 / 50 Filter:
       - Bullish (EMA21 > EMA50): ONLY LONG signals allowed.
       - Bearish (EMA21 < EMA50): ONLY SHORT signals allowed.
       - Choppy (|EMA21 - EMA50| / Price < min_spread_pct): REJECTED (Market is flat/ranging).

    Returns:
    --------
    Dict[str, Any] with keys:
        - is_valid: bool
        - reject_reason: Optional[str]
        - htf_trend: str ("BULLISH" | "BEARISH" | "CHOPPY" | "UNKNOWN")
        - ema_21: float
        - ema_50: float
        - spread_pct: float
    """
    sym_clean = str(symbol or "NQ").upper().replace("=F", "").replace("!", "").strip()
    tf_clean = str(timeframe or "1h").lower().strip()

    if tf_clean in ["60m", "60", "1hour", "h1", "1h"]:
        tf_norm = "1h"
    elif tf_clean in ["15min", "m15", "15m", "15"]:
        tf_norm = "15m"
    elif tf_clean in ["4hour", "h4", "4h", "240m", "240"]:
        tf_norm = "4h"
    elif tf_clean in ["daily", "d1", "1d", "1440"]:
        tf_norm = "1d"
    else:
        tf_norm = tf_clean

    # Map micro contracts to parent symbol config
    sym_root = sym_clean
    root_map = {
        "MNQ": "NQ", "MES": "ES", "MYM": "YM", "M2K": "RTY",
        "MCL": "CL", "MGC": "GC", "SIL": "SI"
    }
    if sym_root in root_map:
        sym_root = root_map[sym_root]

    # 1. Check Asset Config and Timeframe Permissions
    cfg = ASSET_CONFIG.get(sym_root)
    if cfg is not None:
        allowed = [str(x).lower().strip() for x in cfg.get("allowed_tfs", [])]
        if not allowed:
            return {
                "is_valid": False,
                "reject_reason": f"ASSET_{sym_clean}_BLACKLISTED ({cfg.get('comment', 'No timeframes permitted')})",
                "htf_trend": "UNKNOWN",
                "ema_21": 0.0,
                "ema_50": 0.0,
                "spread_pct": 0.0
            }

        if tf_clean not in allowed and tf_norm not in allowed:
            return {
                "is_valid": False,
                "reject_reason": f"TIMEFRAME_{tf_clean.upper()}_NOT_ALLOWED_FOR_{sym_clean} ({cfg.get('comment', 'Timeframe not allowed')})",
                "htf_trend": "UNKNOWN",
                "ema_21": 0.0,
                "ema_50": 0.0,
                "spread_pct": 0.0
            }

    # 2. Extract or Compute H4 Data
    h4_candles = pd.DataFrame()
    if df_h4 is not None and not df_h4.empty and len(df_h4) >= 20:
        h4_candles = df_h4.copy()
    elif df_ltf is not None and not df_ltf.empty:
        tcol = "timestamp" if "timestamp" in df_ltf.columns else ("datetime" if "datetime" in df_ltf.columns else None)
        if tcol and len(df_ltf) >= 40:
            try:
                df_temp = df_ltf.copy()
                df_temp[tcol] = pd.to_datetime(df_temp[tcol], utc=True)
                df_resampled = df_temp.set_index(tcol).resample("4h").agg({
                    "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
                }).dropna().reset_index()
                if len(df_resampled) >= 15:
                    h4_candles = df_resampled
            except Exception:
                pass

        if h4_candles.empty and len(df_ltf) >= 20:
            h4_candles = df_ltf.copy()

    if h4_candles.empty or len(h4_candles) < 10:
        return {
            "is_valid": True,
            "reject_reason": None,
            "htf_trend": "UNKNOWN",
            "ema_21": 0.0,
            "ema_50": 0.0,
            "spread_pct": 0.0
        }

    # 3. Compute H4 EMA 21 and EMA 50
    close_series = h4_candles["close"].astype(float)
    last_close = float(close_series.iloc[-1])
    ema_21 = float(close_series.ewm(span=21, adjust=False).mean().iloc[-1])
    ema_50 = float(close_series.ewm(span=50, adjust=False).mean().iloc[-1])

    spread_pct = abs(ema_21 - ema_50) / last_close if last_close > 0 else 0.0

    # 4. Check Choppy / Flat Market
    if spread_pct < min_spread_pct:
        htf_trend = "CHOPPY"
        return {
            "is_valid": False,
            "reject_reason": f"H4_TREND_CHOPPY_FLAT_EMAS (Spread: {spread_pct*100:.4f}% < {min_spread_pct*100:.4f}%)",
            "htf_trend": htf_trend,
            "ema_21": round(ema_21, 2),
            "ema_50": round(ema_50, 2),
            "spread_pct": round(spread_pct, 6)
        }

    # 5. Determine Trend Direction
    if ema_21 > ema_50:
        htf_trend = "BULLISH"
    else:
        htf_trend = "BEARISH"

    # 6. Trend Direction Alignment Check
    dir_upper = str(direction).upper()
    if dir_upper == "LONG" and htf_trend != "BULLISH":
        return {
            "is_valid": False,
            "reject_reason": f"LONG_SIGNAL_CONTRADICTS_H4_EMA_{htf_trend}_TREND (EMA21: {ema_21:.2f} < EMA50: {ema_50:.2f})",
            "htf_trend": htf_trend,
            "ema_21": round(ema_21, 2),
            "ema_50": round(ema_50, 2),
            "spread_pct": round(spread_pct, 6)
        }
    elif dir_upper == "SHORT" and htf_trend != "BEARISH":
        return {
            "is_valid": False,
            "reject_reason": f"SHORT_SIGNAL_CONTRADICTS_H4_EMA_{htf_trend}_TREND (EMA21: {ema_21:.2f} > EMA50: {ema_50:.2f})",
            "htf_trend": htf_trend,
            "ema_21": round(ema_21, 2),
            "ema_50": round(ema_50, 2),
            "spread_pct": round(spread_pct, 6)
        }
    elif dir_upper == "NEUTRAL":
        return {
            "is_valid": False,
            "reject_reason": "SIGNAL_DIRECTION_IS_NEUTRAL",
            "htf_trend": htf_trend,
            "ema_21": round(ema_21, 2),
            "ema_50": round(ema_50, 2),
            "spread_pct": round(spread_pct, 6)
        }

    # 7. Volatility Regime Filter (ATR Filter)
    if df_ltf is not None and not df_ltf.empty and len(df_ltf) >= 16:
        is_vol_ok, cur_atr, req_atr = is_volatility_sufficient(
            df=df_ltf,
            period=14,
            sma_period=50,
            threshold_multiplier=0.85
        )
        if not is_vol_ok:
            return {
                "is_valid": False,
                "reject_reason": f"LOW_VOLATILITY_REGIME (Current ATR: {cur_atr:.4f} < Required: {req_atr:.4f})",
                "htf_trend": htf_trend,
                "ema_21": round(ema_21, 2),
                "ema_50": round(ema_50, 2),
                "spread_pct": round(spread_pct, 6),
                "current_atr": round(cur_atr, 4),
                "required_atr": round(req_atr, 4)
            }

    return {
        "is_valid": True,
        "reject_reason": None,
        "htf_trend": htf_trend,
        "ema_21": round(ema_21, 2),
        "ema_50": round(ema_50, 2),
        "spread_pct": round(spread_pct, 6)
    }


def evaluate_ict_combo_fixed(df: pd.DataFrame, df_htf: Optional[pd.DataFrame] = None,
                             proximity_pct: float = None,
                              market_type: str = 'futures',
                              require_killzone: bool = True,
                              strict_htf_alignment: bool = True,
                              symbol: Optional[str] = None,
                              timeframe: Optional[str] = None) -> Dict[str, Any]:
    """Evaluate all 6 ICT models with MARKET TYPE SUPPORT and STRICT HTF / KILLZONE / EMA 21/50 FILTERS."""
    if df is None or df.empty or len(df) < 10:
        return {"signal": None, "direction": "NEUTRAL", "confluence_score": 0.0, "details": {}}

    last_row = df.iloc[-1]
    last_close = float(last_row["close"])
    last_time = pd.to_datetime(last_row["timestamp"]) if "timestamp" in last_row else pd.Timestamp.now()

    # 0. KILLZONE & NEWS BLACKOUT CHECK
    from services.news_filter import is_news_event_window, is_volatility_spike_unsafe

    if is_news_event_window(last_time):
        return {
            "direction": "NEUTRAL",
            "confluence_score": 0.0,
            "details": {"reject_reason": "NEWS_EVENT_BLACKOUT_WINDOW"}
        }

    if is_volatility_spike_unsafe(df):
        return {
            "direction": "NEUTRAL",
            "confluence_score": 0.0,
            "details": {"reject_reason": "EXTREME_UNSAFE_VOLATILITY_SPIKE"}
        }

    if require_killzone and not is_in_trading_killzone(last_time):
        return {
            "direction": "NEUTRAL",
            "confluence_score": 0.0,
            "details": {"reject_reason": "OFF_HOURS_NON_KILLZONE"}
        }

    params = get_params(market_type)
    if proximity_pct is None:
        proximity_pct = params['proximity_pct']

    # 1. Base Detections with MARKET TYPE
    fvgs = detect_fvg(df, market_type=market_type)
    sweeps = detect_liquidity_sweep(df, swing_window=params['liquidity_swing_window'],
                                    market_type=market_type,
                                    volume_filter=(market_type != 'crypto'))
    asian_sweep = detect_asian_range_sweep(df)
    mss_list = detect_mss(df, market_type=market_type)
    order_blocks = detect_orderblocks(df, market_type=market_type)
    breaker_blocks = detect_breaker_blocks(df, market_type=market_type, precomputed_orderblocks=order_blocks)
    unicorns = detect_unicorn(
        df, 
        market_type=market_type, 
        precomputed_fvgs=fvgs,
        precomputed_breakers=breaker_blocks if market_type == 'futures' else None
    )
    amd_info = detect_amd(df)
    silver_bullets = detect_silver_bullet(df, market_type=market_type, precomputed_fvgs=fvgs)
    
    # 2. HTF Trend Bias Determination
    htf_data = df_htf if df_htf is not None and not df_htf.empty else df
    htf_info = determine_htf_bias(htf_data, strict_mode=strict_htf_alignment, current_timestamp=last_time)

    try:
        ote_levels = calculate_ote_zone(df)
    except Exception:
        ote_levels = (0.0, 0.0, 0.0)

    ote_levels_long = ote_levels
    ote_levels_short = ote_levels

    in_ote_long = is_price_in_ote(last_close, ote_levels_long)
    in_ote_short = is_price_in_ote(last_close, ote_levels_short)
    in_ote = in_ote_long or in_ote_short
    ote_levels = ote_levels_long  # Default for backward compat

    # 3. FILTER: Only count zones near current price
    fvgs_near = filter_fvgs_by_proximity(fvgs, last_close, proximity_pct)
    obs_near = filter_orderblocks_by_proximity(order_blocks, last_close, proximity_pct)

    # 4. Score Bullish vs Bearish Confluence
    bullish_points = 0
    bearish_points = 0
    total_checks = 7

    # Model 1: ICT 2022 Mentorship (Sweep + MSS + FVG)
    fresh_fvgs_near = [f for f in fvgs_near if not f.get("mitigated", False)]
    recent_fvg_bullish = any(f["type"] == "bullish" for f in fresh_fvgs_near)
    recent_fvg_bearish = any(f["type"] == "bearish" for f in fresh_fvgs_near)
    recent_mss_bullish = any(m["type"] == "bullish" for m in mss_list)
    recent_mss_bearish = any(m["type"] == "bearish" for m in mss_list)
    rejected_sweeps = [s for s in sweeps if s.get("rejected", False)]
    recent_sweep_bullish = any(s["type"] == "bullish" for s in rejected_sweeps)
    recent_sweep_bearish = any(s["type"] == "bearish" for s in rejected_sweeps)

    if recent_sweep_bullish and recent_mss_bullish and recent_fvg_bullish:
        bullish_points += 1
    if recent_sweep_bearish and recent_mss_bearish and recent_fvg_bearish:
        bearish_points += 1

    # Model 2: Silver Bullet
    if any(sb["type"] == "bullish" for sb in silver_bullets):
        bullish_points += 1
    if any(sb["type"] == "bearish" for sb in silver_bullets):
        bearish_points += 1

    # Model 3: Power of 3 (AMD)
    if amd_info and amd_info.get("manipulation_detected"):
        if amd_info.get("manipulation_type") == "bullish":
            bullish_points += 1
        elif amd_info.get("manipulation_type") == "bearish":
            bearish_points += 1

    # Model 4: Direction-Aware OTE Alignment
    if in_ote_long and recent_fvg_bullish:
        bullish_points += 1
    if in_ote_short and recent_fvg_bearish:
        bearish_points += 1

    # Model 5: Unicorn Model (Breaker + FVG)
    if any(u["type"] == "bullish" for u in unicorns):
        bullish_points += 1
    if any(u["type"] == "bearish" for u in unicorns):
        bearish_points += 1

    # Model 6: MMBM / MMSM (HTF Bias)
    htf_bias_dir = htf_info.get("bias", "NEUTRAL")
    if htf_bias_dir == "BULLISH":
        bullish_points += 1
    elif htf_bias_dir == "BEARISH":
        bearish_points += 1

    # Model 7: Asian Session Range Sweep (Judas Swing)
    if asian_sweep and asian_sweep.get("has_asian_sweep"):
        if asian_sweep.get("sweep_type") == "bullish":
            bullish_points += 1
        elif asian_sweep.get("sweep_type") == "bearish":
            bearish_points += 1

    # Determine winning direction (min 3 confluence points required for signal)
    if bullish_points > bearish_points and bullish_points >= 3:
        direction = "LONG"
        confluence_score = min(0.95, 0.50 + (bullish_points / total_checks) * 0.45)
    elif bearish_points > bullish_points and bearish_points >= 3:
        direction = "SHORT"
        confluence_score = min(0.95, 0.50 + (bearish_points / total_checks) * 0.45)
    else:
        direction = "NEUTRAL"
        confluence_score = 0.30

    # STRICT HTF ALIGNMENT ENFORCEMENT
    if strict_htf_alignment:
        if htf_bias_dir == "NEUTRAL":
            direction = "NEUTRAL"
            confluence_score = 0.15
        elif htf_bias_dir == "BULLISH" and direction == "SHORT":
            direction = "NEUTRAL"
            confluence_score = 0.15
        elif htf_bias_dir == "BEARISH" and direction == "LONG":
            direction = "NEUTRAL"
            confluence_score = 0.15

    # 5. ASSET & H4 EMA 21/50 TREND VALIDATION
    asset_validation = is_valid_signal_for_asset(
        symbol=symbol or "NQ",
        timeframe=timeframe or "1h",
        direction=direction,
        df_h4=df_htf,
        df_ltf=df
    )

    if not asset_validation["is_valid"] and direction != "NEUTRAL":
        reject_reason = asset_validation.get("reject_reason", "ASSET_VALIDATION_FAILED")
        direction = "NEUTRAL"
        confluence_score = 0.15
    else:
        reject_reason = None

    details = {
        "fvgs": fvgs,
        "fvgs_near": fvgs_near,
        "fvgs_total": len(fvgs),
        "fvgs_near_count": len(fvgs_near),
        "sweeps": sweeps,
        "mss": mss_list,
        "order_blocks": order_blocks,
        "order_blocks_near": obs_near,
        "breaker_blocks": breaker_blocks,
        "unicorns": unicorns,
        "amd": amd_info,
        "silver_bullets": silver_bullets,
        "htf_bias": htf_info,
        "ote": ote_levels,
        "in_ote": in_ote,
        "bullish_points": bullish_points,
        "bearish_points": bearish_points,
        "proximity_pct": proximity_pct,
        "market_type": market_type,
        "is_killzone": is_in_trading_killzone(last_time),
        "asset_validation": asset_validation,
        "reject_reason": reject_reason,
        "h4_ema_21": asset_validation.get("ema_21", 0.0),
        "h4_ema_50": asset_validation.get("ema_50", 0.0),
        "h4_trend": asset_validation.get("htf_trend", "UNKNOWN")
    }

    return {
        "direction": direction,
        "confluence_score": round(confluence_score, 4),
        "details": details
    }
