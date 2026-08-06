"""XGBoost Hyperparameter Optimization using Optuna.
"""

import os
import logging
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

try:
    import optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False


def optimize_xgboost_params(X: pd.DataFrame, y: pd.Series, n_trials: int = 25) -> dict:
    """Find best XGBoost parameters using Optuna hyperparameter search."""
    if not OPTUNA_AVAILABLE:
        logging.warning("Optuna is not installed. Returning default tuned hyperparameters.")
        return {
            "n_estimators": 150,
            "max_depth": 5,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42
        }

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 50, 300),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "random_state": 42,
            "eval_metric": "logloss"
        }

        clf = xgb.XGBClassifier(**params)
        clf.fit(X_train, y_train)

        preds = clf.predict(X_val)
        score = f1_score(y_val, preds, zero_division=0)
        return score

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, timeout=60)

    best_params = study.best_params
    best_params["random_state"] = 42
    best_params["eval_metric"] = "logloss"

    logging.info(f"Optuna Best Parameters found (F1 Score: {study.best_value:.4f}): {best_params}")
    return best_params
