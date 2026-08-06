"""Universal Multi-Asset & Multi-Timeframe XGBoost Model Trainer.

Combines historical datasets from multiple assets (NQ, SP/ES, BTC, Gold GC1!, YM1!)
and multiple timeframes (5m, 15m, 1h) into a single unified dataset to prevent
overfitting and learn universal ICT market mechanics across asset classes.
"""

import os
import sys
import glob
import logging
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
import joblib

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.features import extract_features
from strategy.combo import evaluate_ict_combo

MODEL_PATH = "ml_model.json"
TIMEFRAMES = ["5min", "15min", "1h"]


def standardize_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names to ['timestamp', 'open', 'high', 'low', 'close', 'volume']."""
    rename_dict = {}
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if "time" in col_lower or "date" in col_lower:
            rename_dict[col] = "timestamp"
        elif col_lower in ["open", "o"] or col_lower.startswith("open"):
            rename_dict[col] = "open"
        elif col_lower in ["high", "h"] or col_lower.startswith("high"):
            rename_dict[col] = "high"
        elif col_lower in ["low", "l"] or col_lower.startswith("low"):
            rename_dict[col] = "low"
        elif col_lower in ["close", "c"] or col_lower.startswith("close"):
            rename_dict[col] = "close"
        elif "vol" in col_lower:
            rename_dict[col] = "volume"

    df = df.rename(columns=rename_dict)

    if "volume" not in df.columns:
        df["volume"] = 100.0

    # Ensure required columns exist
    required = ["timestamp", "open", "high", "low", "close"]
    for req in required:
        if req not in df.columns:
            raise ValueError(f"Missing column: {req}")

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["timestamp", "open", "high", "low", "close"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def resample_timeframe(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Resample candle DataFrame to 5min, 15min, or 1h."""
    df_copy = df.copy()
    df_copy.set_index("timestamp", inplace=True)
    resample_freq = timeframe.replace("T", "min")
    resampled = df_copy.resample(resample_freq).agg({
        "open": lambda x: x.iloc[0] if len(x) > 0 else np.nan,
        "high": "max",
        "low": "min",
        "close": lambda x: x.iloc[-1] if len(x) > 0 else np.nan,
        "volume": "sum"
    }).dropna().reset_index()
    return resampled


def extract_labeled_features_from_df(df: pd.DataFrame, asset_label: str, tf_label: str, future_lookahead: int = 12) -> pd.DataFrame:
    """Extract ICT features and future labels for a single asset dataframe."""
    warmup = 50
    total_len = len(df)
    if total_len <= warmup + future_lookahead:
        return pd.DataFrame()

    records = []
    step = max(1, (total_len - warmup - future_lookahead) // 2500)

    for i in range(warmup, total_len - future_lookahead, step):
        df_slice = df.iloc[i - warmup:i + 1].copy()

        combo_res = evaluate_ict_combo(df_slice)
        features_df = extract_features(df_slice, combo_res["details"])
        features = features_df.iloc[0].to_dict()

        entry_price = float(df_slice.iloc[-1]["close"])
        future_slice = df.iloc[i + 1: i + 1 + future_lookahead]

        tp_target = entry_price * 1.0035
        sl_target = entry_price * 0.9965

        target = 0
        for _, row in future_slice.iterrows():
            high = float(row["high"])
            low = float(row["low"])

            if low <= sl_target:
                target = 0
                break
            if high >= tp_target:
                target = 1
                break

        features["target"] = target
        features["asset"] = asset_label
        features["timeframe"] = tf_label
        records.append(features)

    return pd.DataFrame(records)


def build_universal_dataset() -> pd.DataFrame:
    """Find all available CSV files and build unified multi-asset dataset."""
    search_dirs = [
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # loyiha/
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # workspace root
    ]

    found_files = []
    for s_dir in search_dirs:
        found_files.extend(glob.glob(os.path.join(s_dir, "*.csv")))
        found_files.extend(glob.glob(os.path.join(s_dir, "data", "*.csv")))

    found_files = list(set(found_files))
    logging.info(f"Universal Model: Found {len(found_files)} potential CSV dataset files.")

    all_records = []

    for f_path in found_files:
        filename = os.path.basename(f_path)
        if filename.startswith("preview") or filename.startswith("scratch"):
            continue

        logging.info(f"Processing CSV dataset: {filename}...")

        try:
            df_raw = pd.read_csv(f_path, sep=None, engine='python')
            df_clean = standardize_and_clean(df_raw)

            asset_name = filename.replace(".csv", "").split("_")[0]

            for tf in TIMEFRAMES:
                try:
                    df_tf = resample_timeframe(df_clean, tf)
                    df_features = extract_labeled_features_from_df(df_tf, asset_name, tf)
                    if not df_features.empty:
                        all_records.append(df_features)
                        logging.info(f" -> Asset '{asset_name}' ({tf}): {len(df_features)} samples added.")
                except Exception as e:
                    logging.warning(f" -> Skipping timeframe {tf} for {filename}: {e}")

        except Exception as e:
            logging.warning(f"Could not process CSV {filename}: {e}")

    if not all_records:
        logging.error("No valid features could be extracted from CSV files.")
        return pd.DataFrame()

    universal_df = pd.concat(all_records, ignore_index=True)
    logging.info(f"Universal Dataset Built! Total Samples: {len(universal_df)}")
    return universal_df


def train_universal_model():
    """Train XGBoost Classifier on Universal Multi-Asset Multi-Timeframe Dataset."""
    logging.info("Starting Universal Multi-Asset Model Training...")

    df_universal = build_universal_dataset()
    if df_universal.empty:
        logging.error("Universal training aborted: Dataset is empty.")
        return

    feature_cols = [c for c in df_universal.columns if c not in ["target", "asset", "timeframe"]]

    X = df_universal[feature_cols]
    y = df_universal["target"]

    split_idx = int(len(df_universal) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    logging.info("Training Universal XGBoost Classifier on %d samples...", len(X))
    model = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42
    )

    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    probas = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, preds)
    f1 = f1_score(y_test, preds, zero_division=0)
    precision = precision_score(y_test, preds, zero_division=0)
    recall = recall_score(y_test, preds, zero_division=0)

    try:
        auc = roc_auc_score(y_test, probas)
    except ValueError:
        auc = 0.5

    logging.info("==================================================")
    logging.info("🌟 UNIVERSAL MULTI-ASSET MODEL TRAINING RESULTS 🌟")
    logging.info(f" -> Total Samples: {len(X)}")
    logging.info(f" -> Accuracy:      {acc:.4f}")
    logging.info(f" -> F1-Score:      {f1:.4f}")
    logging.info(f" -> Precision:     {precision:.4f}")
    logging.info(f" -> Recall:        {recall:.4f}")
    logging.info(f" -> ROC-AUC:       {auc:.4f}")
    logging.info("==================================================")

    joblib.dump(model, MODEL_PATH)
    logging.info(f"Universal Model saved successfully to {MODEL_PATH}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    train_universal_model()
