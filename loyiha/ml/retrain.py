"""Automated Retraining Pipeline with Production Model Gate & Version Registry.

Fetches labelled trade outcomes, extracts historical features without data leakage,
evaluates Candidate Model against Current Model using validation metrics,
and promotes to production only if statistical edge criteria are met.
"""

import os
import sys
import shutil
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np
import joblib
import xgboost as xgb
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score, precision_score

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MODEL_PATH
from data.database import get_session, PaperTrade, IndicatorSnapshot
from ml.tune import optimize_xgboost_params
from ml.features import extract_features

BACKUP_MODEL_PATH = "ml_model_backup.json"
MODEL_REGISTRY_DIR = "ml/models"


def evaluate_model_metrics(model: Any, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
    """Calculates statistical and trading decision metrics for model gate."""
    if len(X) == 0 or len(y) == 0:
        return {"brier_score": 1.0, "log_loss": 1.0, "roc_auc": 0.5, "precision": 0.0, "expectancy": -1.0}

    probas = model.predict_proba(X)[:, 1] if hasattr(model, "predict_proba") else model.predict(xgb.DMatrix(X))
    preds = (probas >= 0.60).astype(int)

    brier = float(brier_score_loss(y, probas))
    ll = float(log_loss(y, probas, labels=[0, 1]))

    try:
        auc = float(roc_auc_score(y, probas))
    except Exception:
        auc = 0.5

    prec = float(precision_score(y, preds, zero_division=0))

    # Trading Expectancy at 0.60 threshold (2R TP, 1R SL)
    trades = int(preds.sum())
    if trades > 0:
        wins = int(y[preds == 1].sum())
        win_rate = wins / trades
        expectancy = (win_rate * 2.0) - ((1.0 - win_rate) * 1.0)
    else:
        expectancy = 0.0

    return {
        "brier_score": round(brier, 4),
        "log_loss": round(ll, 4),
        "roc_auc": round(auc, 4),
        "precision": round(prec, 4),
        "expectancy": round(expectancy, 3),
        "trades": trades
    }


def should_promote_to_production(
    candidate_metrics: Dict[str, float],
    current_metrics: Optional[Dict[str, float]]
) -> Tuple[bool, str]:
    """Evaluates whether Candidate Model qualifies for production deployment."""
    # Absolute quality gates
    if candidate_metrics["expectancy"] <= 0.0:
        return False, f"Negative or zero expectancy ({candidate_metrics['expectancy']} R)"
    if candidate_metrics["brier_score"] > 0.25:
        return False, f"Poor probability calibration (Brier score {candidate_metrics['brier_score']} > 0.25)"

    if current_metrics is None:
        return True, "Initial model deployment meeting quality gates"

    # Comparative evaluation: Candidate must match or improve expectancy without severe degradation
    if candidate_metrics["expectancy"] < current_metrics["expectancy"] - 0.05:
        return False, (
            f"Candidate expectancy ({candidate_metrics['expectancy']} R) is worse than "
            f"current production ({current_metrics['expectancy']} R)"
        )

    if candidate_metrics["log_loss"] > current_metrics["log_loss"] * 1.15:
        return False, (
            f"Candidate log loss ({candidate_metrics['log_loss']}) exceeds current model by >15%"
        )

    return True, "Candidate demonstrates superior/equal edge and passed all quality gates"


def rollback_model() -> bool:
    """Restores the previous production model from backup."""
    if not os.path.exists(BACKUP_MODEL_PATH):
        logging.error("Model Rollback failed: No backup model found at %s", BACKUP_MODEL_PATH)
        return False

    shutil.copyfile(BACKUP_MODEL_PATH, MODEL_PATH)
    logging.info("Model Rollback SUCCESS: Restored %s from %s", MODEL_PATH, BACKUP_MODEL_PATH)
    return True


def run_auto_retrain(min_trades: int = 15) -> bool:
    """Executes automated model retraining, temporal validation, and gated promotion."""
    session = get_session()
    try:
        trades = session.query(PaperTrade).filter(PaperTrade.status != "OPEN").order_by(PaperTrade.created_at.asc()).all()
        if not trades or len(trades) < min_trades:
            logging.warning("Insufficient trade history (%d < %d) for retraining.", len(trades) if trades else 0, min_trades)
            return False

        # Load snapshots and build feature set
        snapshots = session.query(IndicatorSnapshot).order_by(IndicatorSnapshot.timestamp.asc()).all()
        if not snapshots:
            logging.warning("No indicator snapshots found for feature alignment.")
            return False

        # Prepare chronologically aligned dataset
        records = []
        for s in snapshots:
            d = s.__dict__.copy()
            d.pop("_sa_instance_state", None)
            records.append(d)

        df = pd.DataFrame(records)
        if df.empty or "target" not in df.columns:
            logging.warning("Indicator snapshot data empty or missing target.")
            return False

        feature_cols = sorted([c for c in df.columns if c not in ["target", "timestamp", "pair", "id", "created_at"]])
        X = df[feature_cols]
        y = df["target"]

        # Chronological Train (75%) vs Validation (25%) split
        split_idx = int(len(df) * 0.75)
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

        # Train Candidate Model
        candidate_clf = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.03,
            eval_metric="logloss",
            random_state=42
        )
        candidate_clf.fit(X_train, y_train)

        # Evaluate Candidate vs Current
        candidate_metrics = evaluate_model_metrics(candidate_clf, X_val, y_val)
        current_metrics = None

        if os.path.exists(MODEL_PATH):
            try:
                curr_clf = joblib.load(MODEL_PATH)
                # Align feature columns with existing model's expected order
                if hasattr(curr_clf, 'get_booster'):
                    model_feature_names = curr_clf.get_booster().feature_names
                    if model_feature_names:
                        aligned_cols = [c for c in model_feature_names if c in X_val.columns]
                        if len(aligned_cols) == len(model_feature_names):
                            X_val_aligned = X_val[aligned_cols]
                        else:
                            X_val_aligned = X_val
                    else:
                        X_val_aligned = X_val
                else:
                    X_val_aligned = X_val
                current_metrics = evaluate_model_metrics(curr_clf, X_val_aligned, y_val)
            except Exception as e:
                logging.warning("Could not evaluate existing model: %s", e)

        # Production Gate Evaluation
        promote, reason = should_promote_to_production(candidate_metrics, current_metrics)
        logging.info("Model Gate Decision: %s (Reason: %s)", "PROMOTE" if promote else "REJECT", reason)

        if promote:
            # Backup existing model
            if os.path.exists(MODEL_PATH):
                shutil.copyfile(MODEL_PATH, BACKUP_MODEL_PATH)

            # Register versioned copy
            os.makedirs(MODEL_REGISTRY_DIR, exist_ok=True)
            version_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
            version_path = os.path.join(MODEL_REGISTRY_DIR, f"ml_model_v{version_tag}.joblib")
            joblib.dump(candidate_clf, version_path)

            # Deploy to production path
            joblib.dump(candidate_clf, MODEL_PATH)
            logging.info("Deployed new model to %s (Version: %s)", MODEL_PATH, version_tag)
            return True
        else:
            logging.info("Candidate model rejected. Keeping existing production model.")
            return False

    except Exception as e:
        logging.error("Auto-retraining failed with error: %s", e)
        return False
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_auto_retrain()
