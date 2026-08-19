"""Walk-Forward Validation, Probability Calibration, and Market Regime Analytics.

Provides rigorous, lookahead-free evaluation of the XGBoost decision gate.
"""

from typing import Dict, List, Any, Tuple
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, precision_recall_curve, auc
)


def run_walk_forward_validation(
    df: pd.DataFrame,
    feature_cols: List[str],
    n_splits: int = 5,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2
) -> List[Dict[str, Any]]:
    """Performs chronological walk-forward validation on time-series dataset.

    Fold sequence:
    [ Train ] -> [ Validation ] -> [ Test ]
    Expanding window step-by-step.
    """
    total_len = len(df)
    if total_len < 100:
        raise ValueError("Dataset too small for walk-forward validation (min 100 rows required).")

    fold_results = []
    step_size = int(total_len * (1.0 - train_ratio) / n_splits)

    for fold in range(n_splits):
        train_end = int(total_len * train_ratio) + (fold * step_size)
        val_end = min(total_len, train_end + int(step_size * 0.5))
        test_end = min(total_len, val_end + step_size)

        if test_end <= val_end or train_end >= total_len:
            break

        train_df = df.iloc[:train_end]
        val_df = df.iloc[train_end:val_end]
        test_df = df.iloc[val_end:test_end]

        X_train, y_train = train_df[feature_cols], train_df["target"]
        X_val, y_val = val_df[feature_cols], val_df["target"]
        X_test, y_test = test_df[feature_cols], test_df["target"]

        # Calculate scale_pos_weight for class imbalance
        pos_count = (y_train == 1).sum()
        neg_count = (y_train == 0).sum()
        scale_pos = (neg_count / pos_count) if pos_count > 0 else 1.0

        base_clf = XGBClassifier(
            n_estimators=120,
            max_depth=4,
            learning_rate=0.03,
            scale_pos_weight=scale_pos,
            eval_metric="logloss",
            random_state=42
        )
        base_clf.fit(X_train, y_train)

        # Calibrate using Validation set if possible, otherwise use sigmoid cv
        try:
            calibrated_clf = CalibratedClassifierCV(estimator=base_clf, method="sigmoid", cv="prefit")
            calibrated_clf.fit(X_val, y_val)
        except Exception:
            calibrated_clf = base_clf

        probas = calibrated_clf.predict_proba(X_test)[:, 1]
        preds = (probas >= 0.55).astype(int)

        acc = accuracy_score(y_test, preds)
        prec = precision_score(y_test, preds, zero_division=0)
        rec = recall_score(y_test, preds, zero_division=0)
        f1 = f1_score(y_test, preds, zero_division=0)

        try:
            roc_auc = roc_auc_score(y_test, probas)
        except Exception:
            roc_auc = 0.5

        try:
            p_curve, r_curve, _ = precision_recall_curve(y_test, probas)
            pr_auc = auc(r_curve, p_curve)
        except Exception:
            pr_auc = 0.5

        # Trade economics on Test Fold
        trades = len(preds[preds == 1])
        wins = int((preds[preds == 1] == y_test[preds == 1]).sum()) if trades > 0 else 0
        losses = trades - wins
        win_rate = (wins / trades * 100.0) if trades > 0 else 0.0

        # R calculations with 1:2 RRR (2R win, -1R loss)
        total_r = (wins * 2.0) - (losses * 1.0)
        avg_r = (total_r / trades) if trades > 0 else 0.0
        expectancy = ((win_rate / 100.0) * 2.0) - (((100.0 - win_rate) / 100.0) * 1.0)
        profit_factor = ((wins * 2.0) / (losses * 1.0)) if losses > 0 else (99.0 if wins > 0 else 0.0)

        fold_results.append({
            "fold": fold + 1,
            "train_samples": len(train_df),
            "test_samples": len(test_df),
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "trades": trades,
            "win_rate": round(win_rate, 2),
            "total_r": round(total_r, 2),
            "avg_r": round(avg_r, 2),
            "expectancy": round(expectancy, 3),
            "profit_factor": round(profit_factor, 2)
        })

    return fold_results


def evaluate_calibration_bins(
    y_true: np.ndarray,
    y_probas: np.ndarray
) -> List[Dict[str, Any]]:
    """Evaluates probability calibration accuracy across 5 confidence bins."""
    bins = [
        (0.50, 0.60),
        (0.60, 0.70),
        (0.70, 0.80),
        (0.80, 0.90),
        (0.90, 1.00)
    ]
    results = []

    for low, high in bins:
        mask = (y_probas >= low) & (y_probas < high if high < 1.0 else y_probas <= high)
        bin_count = int(mask.sum())
        if bin_count > 0:
            bin_wins = int(y_true[mask].sum())
            real_win_rate = (bin_wins / bin_count) * 100.0
            avg_r = ((bin_wins * 2.0) - ((bin_count - bin_wins) * 1.0)) / bin_count
        else:
            real_win_rate = 0.0
            avg_r = 0.0

        results.append({
            "bin": f"{int(low*100)}%-{int(high*100)}%",
            "signals": bin_count,
            "real_win_rate": round(real_win_rate, 2),
            "avg_r": round(avg_r, 2)
        })

    return results


def optimize_confidence_thresholds(
    y_true: np.ndarray,
    y_probas: np.ndarray
) -> List[Dict[str, Any]]:
    """Backtests various probability decision thresholds from 0.50 to 0.85."""
    thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]
    results = []

    for th in thresholds:
        active_mask = y_probas >= th
        trades = int(active_mask.sum())
        if trades == 0:
            results.append({
                "threshold": th,
                "trades": 0,
                "win_rate": 0.0,
                "expectancy": 0.0,
                "profit_factor": 0.0,
                "total_r": 0.0
            })
            continue

        wins = int(y_true[active_mask].sum())
        losses = trades - wins
        win_rate = (wins / trades) * 100.0
        total_r = (wins * 2.0) - (losses * 1.0)
        expectancy = ((win_rate / 100.0) * 2.0) - (((100.0 - win_rate) / 100.0) * 1.0)
        profit_factor = (wins * 2.0) / (losses * 1.0) if losses > 0 else (99.0 if wins > 0 else 0.0)

        results.append({
            "threshold": th,
            "trades": trades,
            "win_rate": round(win_rate, 2),
            "expectancy": round(expectancy, 3),
            "profit_factor": round(profit_factor, 2),
            "total_r": round(total_r, 2)
        })

    return results


def calculate_strategy_breakdown(
    df: pd.DataFrame,
    y_probas: np.ndarray
) -> Dict[str, Dict[str, Any]]:
    """Segments performance by ICT strategy setup (Unicorn, Silver Bullet, Sweep, MSS, OTE)."""
    strategies = {
        "Unicorn": df.get("unicorn_detected", pd.Series(0, index=df.index)) == 1,
        "Silver_Bullet": df.get("silver_bullet_detected", pd.Series(0, index=df.index)) == 1,
        "Liquidity_Sweep": df.get("liquidity_sweep", pd.Series(0, index=df.index)) == 1,
        "MSS": df.get("mss_detected", pd.Series(0, index=df.index)) == 1,
        "OTE": df.get("in_ote", pd.Series(0, index=df.index)) == 1,
    }

    breakdown = {}
    y_true = df["target"].to_numpy()

    for name, mask in strategies.items():
        sub_true = y_true[mask]
        sub_probas = y_probas[mask] if len(y_probas) == len(mask) else np.array([])
        count = len(sub_true)

        if count > 0:
            wins = int(sub_true.sum())
            losses = count - wins
            win_rate = (wins / count) * 100.0
            avg_r = ((wins * 2.0) - (losses * 1.0)) / count
            avg_confidence = float(sub_probas.mean() * 100.0) if len(sub_probas) > 0 else 0.0
        else:
            wins, losses, win_rate, avg_r, avg_confidence = 0, 0, 0.0, 0.0, 0.0

        breakdown[name] = {
            "sample_size": count,
            "win_rate": round(win_rate, 2),
            "avg_r": round(avg_r, 2),
            "avg_confidence": round(avg_confidence, 2)
        }

    return breakdown


def calculate_market_regime_breakdown(
    df: pd.DataFrame,
    y_probas: np.ndarray
) -> Dict[str, Dict[str, Any]]:
    """Evaluates performance under various volatility and session regimes."""
    volatility = df.get("volatility_10", pd.Series(0.0, index=df.index))
    median_vol = float(volatility.median()) if len(volatility) > 0 else 0.0

    session_type = df.get("session_type", pd.Series(3, index=df.index))

    regimes = {
        "High_Volatility": volatility > median_vol,
        "Low_Volatility": volatility <= median_vol,
        "London_Session": session_type == 1,
        "NY_Session": session_type == 2,
        "Asian_OffHours": session_type.isin([0, 3])
    }

    breakdown = {}
    y_true = df["target"].to_numpy()

    for name, mask in regimes.items():
        sub_true = y_true[mask]
        sub_probas = y_probas[mask] if len(y_probas) == len(mask) else np.array([])
        count = len(sub_true)

        if count > 0:
            wins = int(sub_true.sum())
            losses = count - wins
            win_rate = (wins / count) * 100.0
            avg_r = ((wins * 2.0) - (losses * 1.0)) / count
        else:
            win_rate, avg_r = 0.0, 0.0

        breakdown[name] = {
            "samples": count,
            "win_rate": round(win_rate, 2),
            "avg_r": round(avg_r, 2)
        }

    return breakdown
