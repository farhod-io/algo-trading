"""Market-type specific parameter configuration for ICT strategy detection.

Provides adaptive thresholds for crypto vs futures markets.
"""

from typing import Dict, Any


# Default parameters per market type
MARKET_PARAMS: Dict[str, Dict[str, Any]] = {
    "crypto": {
        "liquidity_swing_window": 10,
        "proximity_pct": 0.005,
        "volume_filter": False,
        "description": "Crypto markets (24/7, high volatility, no session filters)",
    },
    "futures": {
        "liquidity_swing_window": 15,
        "proximity_pct": 0.003,
        "volume_filter": True,
        "description": "US Futures (NQ, ES, GC, CL — session-based, institutional flow)",
    },
}

# Fallback defaults
_DEFAULT_PARAMS = {
    "liquidity_swing_window": 10,
    "proximity_pct": 0.005,
    "volume_filter": False,
}


def get_params(market_type: str = "futures") -> Dict[str, Any]:
    """Return market-type specific parameters for ICT indicator detection.

    Parameters
    ----------
    market_type : str
        'crypto' or 'futures'

    Returns
    -------
    Dict[str, Any]
        Configuration parameters for the given market type
    """
    return MARKET_PARAMS.get(market_type, _DEFAULT_PARAMS)
