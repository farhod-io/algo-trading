import os
import sys
import logging
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
import joblib

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.features import extract_features
from indicators.fvg import detect_fvg
from indicators.liquidity import detect_liquidity_sweep
from indicators.mss import detect_mss
from indicators.unicorn import detect_unicorn
from indicators.fibonacci import calculate_ote_zone
from strategy.combo_fixed import evaluate_ict_combo_fixed

MODEL_PATH = "ml_model.json"


def clean_and_load_csv(filepath: str, target_timeframe: str = "15min") -> pd.DataFrame:
    """Loads CSV file, standardizes column names, and resamples to target_timeframe."""
    df = pd.read_csv(filepath, sep=None, engine='python')

    rename_dict = {}
    for col in df.columns:
        col_lower = col.lower().strip()
        if "time" in col_lower or "date" in col_lower:
            rename_dict[col] = "timestamp"
        elif "open" in col_lower:
            rename_dict[col] = "open"
        elif "high" in col_lower:
            rename_dict[col] = "high"
        elif "low" in col_lower:
            rename_dict[col] = "low"
        elif "close" in col_lower:
            rename_dict[col] = "close"
        elif "volume" in col_lower or "vol" in col_lower:
            rename_dict[col] = "volume"

    df = df.rename(columns=rename_dict)

    if "volume" not in df.columns:
        df["volume"] = 100.0

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    time_diff = df["timestamp"].diff().median()
    logging.info(f"Data timeframe median: {time_diff}")

    if time_diff < pd.Timedelta(minutes=5) and target_timeframe not in ["1min", "1T"]:
        logging.info(f"Resampling data to {target_timeframe}...")
        df.set_index("timestamp", inplace=True)
        freq = target_timeframe.replace("T", "min")
        resampled = df.resample(freq).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna().reset_index()
        return resampled

    return df


def generate_labeled_dataset(df: pd.DataFrame, future_lookahead: int = 24) -> pd.DataFrame:
    """Calculates ICT features and causal future price targets without lookahead bias."""
    logging.info("Calculating ICT indicators and features historically with causal sequence...")

    warmup = 50
    records = []

    total_len = len(df)
    step = max(1, (total_len - warmup - future_lookahead) // 5000)

    for i in range(warmup, total_len - future_lookahead, step):
        # Strict historical window slice up to current bar i (NO future data included in features)
        df_slice = df.iloc[i - warmup:i + 1].copy()

        combo_res = evaluate_ict_combo_fixed(df_slice, market_type='futures', require_killzone=False, strict_htf_alignment=True)
        features_df = extract_features(df_slice, combo_res["details"])
        features = features_df.iloc[0].to_dict()

        entry_price = float(df_slice.iloc[-1]["close"])
        future_slice = df.iloc[i + 1: i + 1 + future_lookahead]

        direction = combo_res.get("direction", "LONG")

        # Causal Sequential Trade Simulation (No Lookahead Bias)
        if direction == "LONG":
            tp_target = entry_price * 1.0065  # +0.65%
            sl_target = entry_price * 0.9965  # -0.35%
        else:
            tp_target = entry_price * 0.9935  # -0.65%
            sl_target = entry_price * 1.0035  # +0.35%

        target = 0
        for _, row in future_slice.iterrows():
            high = float(row["high"])
            low = float(row["low"])

            if direction == "LONG":
                if low <= sl_target:
                    target = 0
                    break
                if high >= tp_target:
                    target = 1
                    break
            else:  # SHORT
                if high >= sl_target:
                    target = 0
                    break
                if low <= tp_target:
                    target = 1
                    break

        features["target"] = target
        records.append(features)

    return pd.DataFrame(records)


def train_on_csv(filepath: str, target_timeframe: str = "15min"):
    df_clean = clean_and_load_csv(filepath, target_timeframe)
    logging.info(f"Loaded {len(df_clean)} cleaned rows.")

    df_dataset = generate_labeled_dataset(df_clean)
    if df_dataset.empty:
        logging.error("Failed to generate dataset. Exiting.")
        return

    logging.info(f"Dataset generated. Shape: {df_dataset.shape}")

    feature_cols = [c for c in df_dataset.columns if c != "target"]

    X = df_dataset[feature_cols]
    y = df_dataset["target"]

    # Chronological Split (80% Train, 20% Test)
    split_idx = int(len(df_dataset) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    logging.info("Training XGBoost on historical dataset...")
    model = XGBClassifier(
        n_estimators=150,
        max_depth=5,
        learning_rate=0.03,
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

    logging.info("--- HISTORICAL TRAINING RESULTS ---")
    logging.info(f" -> Accuracy:  {acc:.4f}")
    logging.info(f" -> F1-Score:  {f1:.4f}")
    logging.info(f" -> Precision: {precision:.4f}")
    logging.info(f" -> Recall:    {recall:.4f}")
    logging.info(f" -> ROC-AUC:   {auc:.4f}")

    joblib.dump(model, MODEL_PATH)
    logging.info(f"Model saved successfully to {MODEL_PATH}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    default_path = "../NQ_in_15_minute.csv"
    if len(sys.argv) > 1:
        default_path = sys.argv[1]

    if not os.path.exists(default_path):
        root_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", os.path.basename(default_path))
        if os.path.exists(root_path):
            default_path = root_path
        else:
            logging.error(f"File not found: {default_path}")
            sys.exit(1)

    train_on_csv(default_path, "15min")
