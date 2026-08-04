"""Unicorn Model detection for ICT methodology.

Unicorn Model = Breaker Block + Fair Value Gap (FVG) overlapping in the same price zone.
This is considered one of the highest-probability ICT setups.
"""

from typing import List, Dict
import pandas as pd
from .fvg import detect_fvg
from .orderblock import detect_breaker_blocks


def detect_unicorn(df: pd.DataFrame) -> List[Dict]:
    """Detect Unicorn model setups (Breaker Block + FVG overlap).

    Returns
    -------
    List[Dict]
        List of detected Unicorn setups with keys:
        - type: 'bullish' | 'bearish'
        - fvg: FVG details dict
        - breaker: Breaker Block details dict
        - overlap_low: lower bound of overlapping zone
        - overlap_high: upper bound of overlapping zone
    """
    fvgs = detect_fvg(df)
    breakers = detect_breaker_blocks(df)

    if not fvgs or not breakers:
        return []

    unicorns = []

    for fvg in fvgs:
        for breaker in breakers:
            # Match direction
            if fvg["type"] == breaker["type"]:
                # Check price range intersection
                overlap_low = max(fvg["low"], breaker["low"])
                overlap_high = min(fvg["high"], breaker["high"])

                if overlap_low < overlap_high:  # Valid non-zero price overlap
                    unicorns.append({
                        "type": fvg["type"],
                        "fvg": fvg,
                        "breaker": breaker,
                        "overlap_low": overlap_low,
                        "overlap_high": overlap_high
                    })

    return unicorns
