"""
ICT Rules Mapping Document
This module documents the mathematical definitions and maps the 8 key ICT setups
to the tabular features calculated by indicators and processed by our XGBoost model.
"""

ICT_SETUPS = {
    "Fair Value Gap (FVG)": {
        "definition": "A 3-candle imbalance zone where the wick of candle 1 does not overlap the wick of candle 3.",
        "indicator_module": "indicators.fvg",
        "model_feature": "fvg_detected"
    },
    "Liquidity Sweep (LQ Sweep)": {
        "definition": "Stop hunt price behavior that takes out major swing highs or swing lows and quickly retreats.",
        "indicator_module": "indicators.liquidity",
        "model_feature": "liquidity_sweep"
    },
    "Market Structure Shift (MSS)": {
        "definition": "A shift in trend indicated by displacement that breaks the key swing high or low with body closure.",
        "indicator_module": "indicators.mss",
        "model_feature": "mss_detected"
    },
    "Unicorn Setup": {
        "definition": "An intersection of a Fair Value Gap (FVG) occurring precisely within a Breaker Block zone.",
        "indicator_module": "indicators.unicorn",
        "model_feature": "unicorn_detected"
    },
    "Optimal Trade Entry (OTE)": {
        "definition": "Fibonacci retracement entry zone between 62% (0.62) and 79% (0.79) of the current price swing.",
        "indicator_module": "indicators.fibonacci",
        "model_features": ["ote_low", "ote_mid", "ote_high"]
    },
    "Order Block (OB)": {
        "definition": "The last down-close candle before a strong up move, or the last up-close candle before a strong down move.",
        "indicator_module": "indicators.orderblock",
        "model_feature": None # Detected mathematically in raw structure
    },
    "Silver Bullet": {
        "definition": "A specific trading window setup during high liquidity hours (07:00-08:00, 14:00-15:00, 18:00-19:00 UTC).",
        "indicator_module": "indicators.silver_bullet",
        "model_feature": None # Timeframe filter checked in the scanner
    }
}

def get_setup_details(setup_name: str) -> dict:
    return ICT_SETUPS.get(setup_name, {})
