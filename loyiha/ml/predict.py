"""Prediction wrapper for trained XGBoost model with dynamic hot-reloading and calibrated probability scaling.
"""

import os
import logging
import joblib
import pandas as pd
import numpy as np

MODEL_PATH = "ml_model.json"

_cached_model = None
_cached_mtime = None


def load_model():
    """Hot-reload ML model weights whenever ml_model.json modification timestamp changes."""
    global _cached_model, _cached_mtime

    if not os.path.exists(MODEL_PATH):
        return None

    try:
        current_mtime = os.path.getmtime(MODEL_PATH)
        if _cached_model is None or _cached_mtime != current_mtime:
            logging.info("Hot-reloading updated ML model weights from %s...", MODEL_PATH)
            _cached_model = joblib.load(MODEL_PATH)
            _cached_mtime = current_mtime
        return _cached_model
    except Exception as e:
        logging.error("Failed to load model from %s: %s", MODEL_PATH, e)
        return _cached_model


def predict_signal_confidence(features: pd.DataFrame, rule_confidence: float = 0.80) -> float:
    """Return calibrated prediction confidence score (0-1).

    Parameters
    ----------
    features : pd.DataFrame
        Single-row feature DataFrame
    rule_confidence : float
        Fallback confidence calculated by ICT strategy engine if ML model is unavailable

    Returns
    -------
    float
        Calibrated confidence score between 0.60 (60%) and 0.98 (98%)
    """
    model = load_model()

    if model is None:
        return float(max(0.65, min(0.95, rule_confidence)))

    try:
        features_copy = features.copy()
        if hasattr(model, "feature_names_in_"):
            cols = list(model.feature_names_in_)
            for col in cols:
                if col not in features_copy.columns:
                    features_copy[col] = 0.0
            features_copy = features_copy[cols]

        raw_prob = float(model.predict_proba(features_copy)[0][1])

        # Calibrate ML probability relative to base market distribution
        calibrated_ml = min(0.98, max(0.60, 0.55 + (raw_prob - 0.15) * 1.6))

        # 50/50 Confluence Blend: ICT Rule Engine + ML Calibrated Probability
        final_confidence = (0.50 * float(rule_confidence)) + (0.50 * calibrated_ml)
        return float(min(0.98, max(0.65, final_confidence)))

    except Exception as e:
        logging.error("Failed to predict with ML model: %s. Using rule fallback.", e)
        return float(max(0.65, min(0.95, rule_confidence)))
