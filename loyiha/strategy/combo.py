"""ICT Strategy Combination Engine (combo.py).

Evaluates all 6 ICT Models:
1. ICT 2022 Mentorship Model (Sweep + MSS + FVG)
2. Silver Bullet Model (3 EST Killzones + Sweep + FVG)
3. Power of 3 / AMD Model (Asian Accumulation + London Manipulation + NY Distribution)
4. OTE Model (Fib 0.618 - 0.786 alignment with FVG)
5. Unicorn Model (Breaker Block + FVG overlap)
6. MMBM / MMSM Model (HTF Bias alignment)

Calculates signal confluence, direction, and ICT confidence score.
"""

from typing import Dict, Any, Optional
import pandas as pd

from indicators.fvg import detect_fvg
from indicators.liquidity import detect_liquidity_sweep
from indicators.mss import detect_mss
from indicators.orderblock import detect_orderblocks, detect_breaker_blocks
from indicators.fibonacci import calculate_ote_zone, is_price_in_ote
from indicators.unicorn import detect_unicorn
from indicators.amd import detect_amd
from indicators.silver_bullet import detect_silver_bullet
from indicators.htf_bias import determine_htf_bias


def evaluate_ict_combo(df: pd.DataFrame, df_htf: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Evaluate all 6 ICT models on candle datasets and determine overall signal.

    Parameters
    ----------
    df : pd.DataFrame
        LTF Candle data (5m)
    df_htf : pd.DataFrame, optional
        HTF Candle data (15m/1h) for MTF bias alignment

    Returns
    -------
    Dict[str, Any]
        Confluence assessment dictionary
    """
    if df is None or df.empty or len(df) < 10:
        return {"signal": None, "direction": "NEUTRAL", "confluence_score": 0.0, "details": {}}

    # 1. Base Detections
    fvgs = detect_fvg(df)
    sweeps = detect_liquidity_sweep(df)
    mss_list = detect_mss(df)
    order_blocks = detect_orderblocks(df)
    breaker_blocks = detect_breaker_blocks(df)
    unicorns = detect_unicorn(df)
    amd_info = detect_amd(df)
    silver_bullets = detect_silver_bullet(df)
    htf_info = determine_htf_bias(df_htf if df_htf is not None and not df_htf.empty else df)

    try:
        ote_levels = calculate_ote_zone(df)
    except Exception:
        ote_levels = (0.0, 0.0, 0.0)

    last_close = float(df.iloc[-1]["close"])
    in_ote = is_price_in_ote(last_close, ote_levels)

    # 2. Score Bullish vs Bearish Confluence
    bullish_points = 0
    bearish_points = 0
    total_checks = 6

    # Model 1: ICT 2022 Mentorship (Sweep + MSS + FVG)
    recent_fvg_bullish = any(f["type"] == "bullish" for f in fvgs)
    recent_fvg_bearish = any(f["type"] == "bearish" for f in fvgs)

    recent_mss_bullish = any(m["type"] == "bullish" for m in mss_list)
    recent_mss_bearish = any(m["type"] == "bearish" for m in mss_list)

    recent_sweep_bullish = any(s["type"] == "bullish" for s in sweeps)
    recent_sweep_bearish = any(s["type"] == "bearish" for s in sweeps)

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

    # Model 4: OTE Alignment
    if in_ote and recent_fvg_bullish:
        bullish_points += 1
    if in_ote and recent_fvg_bearish:
        bearish_points += 1

    # Model 5: Unicorn Model (Breaker + FVG)
    if any(u["type"] == "bullish" for u in unicorns):
        bullish_points += 1
    if any(u["type"] == "bearish" for u in unicorns):
        bearish_points += 1

    # Model 6: MMBM / MMSM (HTF Bias)
    if htf_info["bias"] == "BULLISH":
        bullish_points += 1
    elif htf_info["bias"] == "BEARISH":
        bearish_points += 1

    # Determine winning direction and confluence score
    if bullish_points > bearish_points and bullish_points >= 2:
        direction = "LONG"
        confluence_score = min(0.95, 0.50 + (bullish_points / total_checks) * 0.45)
    elif bearish_points > bullish_points and bearish_points >= 2:
        direction = "SHORT"
        confluence_score = min(0.95, 0.50 + (bearish_points / total_checks) * 0.45)
    else:
        direction = "NEUTRAL"
        confluence_score = 0.30

    # 3. Strict HTF Filtering: Reject counter-trend signals when HTF bias is strongly directional
    htf_bias_dir = htf_info.get("bias", "NEUTRAL")
    if htf_bias_dir == "BULLISH" and direction == "SHORT":
        direction = "NEUTRAL"
        confluence_score = 0.20
    elif htf_bias_dir == "BEARISH" and direction == "LONG":
        direction = "NEUTRAL"
        confluence_score = 0.20

    details = {
        "fvgs": fvgs,
        "sweeps": sweeps,
        "mss": mss_list,
        "order_blocks": order_blocks,
        "breaker_blocks": breaker_blocks,
        "unicorns": unicorns,
        "amd": amd_info,
        "silver_bullets": silver_bullets,
        "htf_bias": htf_info,
        "ote": ote_levels,
        "in_ote": in_ote,
        "bullish_points": bullish_points,
        "bearish_points": bearish_points
    }

    return {
        "direction": direction,
        "confluence_score": round(confluence_score, 4),
        "details": details
    }
