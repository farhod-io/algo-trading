import os
import sys
import logging
import pandas as pd
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
import joblib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.dataset_builder import build_dataset

MODEL_PATH = "ml_model.json"


def get_training_data() -> pd.DataFrame:
    """Build dataset from DB snapshots or load pre-generated CSV dataset."""
    df = build_dataset()

    if df.empty:
        csv_path = "ml_dataset.csv"
        if os.path.exists(csv_path):
            logging.info("ML: Loading training dataset from %s", csv_path)
            df = pd.read_csv(csv_path)
        else:
            # Check for NQ CSV in parent directory
            parent_csv = "../NQ_in_15_minute.csv"
            if os.path.exists(parent_csv):
                logging.info("ML: Building training dataset from %s...", parent_csv)
                from ml.train_on_csv import clean_and_load_csv, generate_labeled_dataset
                df_clean = clean_and_load_csv(parent_csv, "15min")
                df = generate_labeled_dataset(df_clean)

    return df


def train() -> None:
    logging.info("ML: Loading training dataset...")
    df = get_training_data()

    if df.empty:
        logging.error("ML Training Aborted: No valid training data found. Please run train_on_csv.py first.")
        return

    feature_cols = [c for c in df.columns if c != "target"]

    X = df[feature_cols]
    y = df["target"]

    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    logging.info("ML: Training XGBoost Classifier on %d samples...", len(df))
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

    logging.info("--- ML TRAINING RESULTS ---")
    logging.info(f" -> Accuracy:  {acc:.4f}")
    logging.info(f" -> F1-Score:  {f1:.4f}")
    logging.info(f" -> Precision: {precision:.4f}")
    logging.info(f" -> Recall:    {recall:.4f}")
    logging.info(f" -> ROC-AUC:   {auc:.4f}")

    joblib.dump(model, MODEL_PATH)
    logging.info(f"ML: Model successfully saved to {MODEL_PATH}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    train()
