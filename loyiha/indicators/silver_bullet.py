"""Silver Bullet Model detection for ICT methodology.

Silver Bullet operates strictly in 3 specific time windows (EST / UTC):
1. London Killzone: 03:00 - 04:00 EST (08:00 - 09:00 UTC)
2. NY Morning Killzone: 10:00 - 11:00 EST (15:00 - 16:00 UTC)
3. NY Afternoon Killzone: 14:00 - 15:00 EST (19:00 - 20:00 UTC)

A valid Silver Bullet setup requires:
- Execution within one of the 3 killzones.
- A liquidity sweep of prior high/low.
- Formation of a fresh FVG in the direction of the reversal.
"""

from datetime import time
from typing import List, Dict, Optional
import pandas as pd

from .fvg import detect_fvg
from .liquidity import detect_liquidity_sweep

SILVER_BULLET_WINDOWS_UTC = [
    {"name": "London Silver Bullet", "start": time(8, 0), "end": time(9, 0)},
    {"name": "NY AM Silver Bullet", "start": time(15, 0), "end": time(16, 0)},
    {"name": "NY PM Silver Bullet", "start": time(19, 0), "end": time(20, 0)},
]


def is_silver_bullet_time(ts: pd.Timestamp) -> Optional[str]:
    """Check if timestamp falls into any of the 3 Silver Bullet windows."""
    t = ts.time()
    for w in SILVER_BULLET_WINDOWS_UTC:
        if w["start"] <= t <= w["end"]:
            return w["name"]
    return None


def detect_silver_bullet(df: pd.DataFrame) -> List[Dict]:
    """Detect Silver Bullet setups.

    Returns
    -------
    List[Dict]
        List of Silver Bullet setups:
        - window: name of the Silver Bullet window
        - type: 'bullish' | 'bearish'
        - fvg: FVG dict
        - sweep: liquidity sweep dict
    """
    setups = []
    if df.empty:
        return setups

    last_ts = pd.to_datetime(df.iloc[-1]["timestamp"])
    sb_window = is_silver_bullet_time(last_ts)

    if not sb_window:
        return setups

    fvgs = detect_fvg(df)
    sweeps = detect_liquidity_sweep(df)

    if not fvgs or not sweeps:
        return setups

    for fvg in fvgs:
        for sweep in sweeps:
            if fvg["type"] == sweep["type"]:
                setups.append({
                    "window": sb_window,
                    "type": fvg["type"],
                    "fvg": fvg,
                    "sweep": sweep,
                    "timestamp": last_ts
                })

    return setups
