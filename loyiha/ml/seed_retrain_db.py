"""Seed DB with realistic IndicatorSnapshot + PaperTrade records from training CSV.

Extracts features from the same pipeline used by combo_fixed → extract_features,
then stores them as IndicatorSnapshot rows with computed targets from trade outcomes.
This allows retrain.py to run end-to-end without data leakage.
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.database import get_session, init_db, IndicatorSnapshot, PaperTrade
from strategy.combo_fixed import evaluate_ict_combo_fixed
from ml.features import extract_features


def seed_retrain_database(csv_path: str = "data/training_btcusdt_15m.csv", num_records: int = 100):
    """Extract features from CSV and insert as IndicatorSnapshot + PaperTrade records."""
    init_db()
    session = get_session()

    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    logging.info("Loaded %d candles from %s", len(df), csv_path)

    warmup = 50
    future_lookahead = 12
    total_len = len(df)

    records_added = 0
    trades_added = 0

    for i in range(warmup, min(total_len - future_lookahead, warmup + num_records + 50)):
        if records_added >= num_records:
            break

        df_slice = df.iloc[i - warmup : i + 1].copy()

        try:
            combo_res = evaluate_ict_combo_fixed(
                df_slice, market_type="futures",
                require_killzone=False, strict_htf_alignment=True
            )
            details = combo_res.get("details", {})
            features_df = extract_features(df_slice, details)
            features = features_df.iloc[0].to_dict()
        except Exception as e:
            logging.warning("Feature extraction failed at idx %d: %s", i, e)
            continue

        entry_price = float(df_slice.iloc[-1]["close"])
        direction = combo_res.get("direction", "LONG")
        future_slice = df.iloc[i + 1 : i + 1 + future_lookahead]

        # Compute target (same logic as train_on_csv)
        if direction == "LONG":
            tp_target = entry_price * 1.0065
            sl_target = entry_price * 0.9965
        else:
            tp_target = entry_price * 0.9935
            sl_target = entry_price * 1.0035

        target = 0
        for _, row in future_slice.iterrows():
            high = float(row["high"])
            low = float(row["low"])
            if direction == "LONG":
                if low <= sl_target and high >= tp_target:
                    target = 0
                    break
                if low <= sl_target:
                    target = 0
                    break
                if high >= tp_target:
                    target = 1
                    break
            else:
                if high >= sl_target and low <= tp_target:
                    target = 0
                    break
                if high >= sl_target:
                    target = 0
                    break
                if low <= tp_target:
                    target = 1
                    break

        ts = df_slice.iloc[-1]["timestamp"]
        if isinstance(ts, pd.Timestamp):
            ts = ts.to_pydatetime()

        # Build IndicatorSnapshot row with all 29 features
        snap = IndicatorSnapshot(
            timestamp=ts,
            pair="BTCUSDT",
            fvg_detected=bool(features.get("fvg_detected", 0)),
            liquidity_sweep=bool(features.get("liquidity_sweep", 0)),
            mss_detected=bool(features.get("mss_detected", 0)),
            unicorn_detected=bool(features.get("unicorn_detected", 0)),
            orderblock_detected=bool(features.get("orderblock_detected", 0)),
            silver_bullet_detected=bool(features.get("silver_bullet_detected", 0)),
            in_ote=bool(features.get("in_ote", 0)),
            ote_low=float(features.get("ote_low", 0.0)),
            ote_mid=float(features.get("ote_mid", 0.0)),
            ote_high=float(features.get("ote_high", 0.0)),
            close_price=float(features.get("close_price", entry_price)),
            fvg_size=float(features.get("fvg_size", 0.0)),
            fvg_distance=float(features.get("fvg_distance", 0.0)),
            candle_body_ratio=float(features.get("candle_body_ratio", 0.0)),
            top_wick_ratio=float(features.get("top_wick_ratio", 0.0)),
            bottom_wick_ratio=float(features.get("bottom_wick_ratio", 0.0)),
            momentum_5=float(features.get("momentum_5", 0.0)),
            momentum_10=float(features.get("momentum_10", 0.0)),
            volatility_10=float(features.get("volatility_10", 0.0)),
            rsi_14=float(features.get("rsi_14", 50.0)),
            atr_14=float(features.get("atr_14", 0.0)),
            atr_ratio=float(features.get("atr_ratio", 0.0)),
            volume_ratio=float(features.get("volume_ratio", 1.0)),
            trend_ema_diff=float(features.get("trend_ema_diff", 0.0)),
            poc_distance=float(features.get("poc_distance", 0.0)),
            dist_to_session_high=float(features.get("dist_to_session_high", 0.0)),
            dist_to_session_low=float(features.get("dist_to_session_low", 0.0)),
            hour_of_day=int(features.get("hour_of_day", 0)),
            session_type=float(features.get("session_type", 0.0)),
            target=target,
        )
        session.add(snap)
        records_added += 1

        # Also add a matching PaperTrade record
        exit_price = tp_target if target == 1 else sl_target
        pnl = (exit_price - entry_price) if direction == "LONG" else (entry_price - exit_price)
        trade = PaperTrade(
            pair="BTCUSDT",
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            stop_loss=sl_target,
            take_profit=tp_target,
            position_size=0.001,
            status="CLOSED",
            pnl=round(pnl, 2),
            created_at=ts,
            closed_at=ts,
        )
        session.add(trade)
        trades_added += 1

        if records_added % 20 == 0:
            session.commit()
            logging.info("  Committed %d records so far...", records_added)

    session.commit()
    session.close()
    logging.info("=== SEED COMPLETE ===")
    logging.info("  IndicatorSnapshots: %d", records_added)
    logging.info("  PaperTrades: %d", trades_added)
    return records_added


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/training_btcusdt_15m.csv"
    seed_retrain_database(csv_path, num_records=200)
