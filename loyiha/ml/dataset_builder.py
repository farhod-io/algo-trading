import os
import sys
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.database import get_session, IndicatorSnapshot
from services.exchange_service import ExchangeFactory
from config import TIMEFRAME

def build_dataset(future_candles_count: int = 12) -> pd.DataFrame:
    """
    Builds a labeled dataset from saved indicator snapshots by looking at future prices.
    Target 1: Price goes up by 0.5% before going down by 0.25% (LONG success).
    Target 0: Otherwise.
    """
    session = get_session()
    try:
        snapshots = session.query(IndicatorSnapshot).order_by(IndicatorSnapshot.timestamp.asc()).all()
        if not snapshots:
            logging.warning("DatasetBuilder: No indicator snapshots found in database.")
            return pd.DataFrame()
            
        logging.info(f"DatasetBuilder: Found {len(snapshots)} snapshots. Fetching future prices...")
        
        # Group by pair
        pairs = set(s.pair for s in snapshots)
        exchange = ExchangeFactory.get_exchange()
        
        # We will fetch a large chunk of historical candles for each pair to align future prices
        # To keep it simple and avoid rate limits, we can also label by looking at subsequent snapshots
        # in the database if they are closely spaced, but fetching from the exchange is much more precise.
        # Let's fetch 500 recent candles for each pair to have a lookup table
        candle_lookups = {}
        for pair in pairs:
            df_candles = exchange.fetch_recent_candles(pair, TIMEFRAME, limit=500)
            if not df_candles.empty:
                df_candles['timestamp'] = pd.to_datetime(df_candles['timestamp'])
                candle_lookups[pair] = df_candles
                
        dataset_records = []
        
        for snap in snapshots:
            pair = snap.pair
            entry_price = snap.close_price
            snap_time = pd.to_datetime(snap.timestamp)
            
            # Find future candles for this snapshot in our lookup
            if pair not in candle_lookups:
                continue
                
            df_pair = candle_lookups[pair]
            
            # Find the row closest to snap_time
            matching_rows = df_pair[df_pair['timestamp'] <= snap_time]
            if matching_rows.empty:
                continue
                
            last_idx = matching_rows.index[-1]
            df_slice = df_pair.loc[:last_idx].tail(50).copy()
            if len(df_slice) < 30:
                continue
                
            indicators = {
                "fvg": snap.fvg_detected,
                "liquidity_sweep": snap.liquidity_sweep,
                "mss": snap.mss_detected,
                "unicorn": snap.unicorn_detected,
                "ote": (snap.ote_low, snap.ote_mid, snap.ote_high)
            }
            
            from ml.features import extract_features
            try:
                features_df = extract_features(df_slice, indicators)
                features = features_df.iloc[0].to_dict()
            except Exception as e:
                logging.error(f"DatasetBuilder: Feature extraction failed for {pair} at {snap_time}: {e}")
                continue
            
            # Future candles are those starting after snap_time
            future_df = df_pair.loc[last_idx+1:].head(future_candles_count)
            
            if len(future_df) < 3: # Not enough future data to label reliably
                continue
                
            direction = getattr(snap, "direction", "LONG") if hasattr(snap, "direction") else "LONG"
            
            if direction == "LONG":
                tp_target = entry_price * 1.0065
                sl_target = entry_price * 0.9965
                target = 0
                for _, row in future_df.iterrows():
                    high = float(row['high'])
                    low = float(row['low'])
                    # Conservative: If both hit in same candle, count as SL first
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
                tp_target = entry_price * 0.9935
                sl_target = entry_price * 1.0035
                target = 0
                for _, row in future_df.iterrows():
                    high = float(row['high'])
                    low = float(row['low'])
                    # Conservative: If both hit in same candle, count as SL first
                    if high >= sl_target and low <= tp_target:
                        target = 0
                        break
                    if high >= sl_target:
                        target = 0
                        break
                    if low <= tp_target:
                        target = 1
                        break
            
            features["target"] = target
            dataset_records.append(features)
            
        df_final = pd.DataFrame(dataset_records)
        logging.info(f"DatasetBuilder: Built dataset with {len(df_final)} rows.")
        return df_final
        
    except Exception as e:
        logging.error(f"DatasetBuilder error: {e}")
        return pd.DataFrame()
    finally:
        session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = build_dataset()
    if not df.empty:
        df.to_csv("ml_dataset.csv", index=False)
        print(df.head())
