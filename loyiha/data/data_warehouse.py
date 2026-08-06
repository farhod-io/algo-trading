import logging
import json
import pandas as pd
from datetime import datetime

from data.database import get_session, IndicatorSnapshot
from indicators.fvg import detect_fvg
from indicators.liquidity import detect_liquidity_sweep
from indicators.mss import detect_mss
from indicators.unicorn import detect_unicorn
from indicators.fibonacci import calculate_ote_zone

def save_indicator_snapshot(df: pd.DataFrame, symbol: str) -> None:
    """Calculates all indicators and saves a snapshot of the current state to the DB."""
    if df.empty:
        return
        
    try:
        # Run indicators
        fvg = detect_fvg(df)
        liquidity = detect_liquidity_sweep(df)
        mss = detect_mss(df)
        unicorn = detect_unicorn(df)
        
        try:
            ote_low, ote_mid, ote_high = calculate_ote_zone(df)
        except Exception:
            ote_low = ote_mid = ote_high = None
            
        close_price = float(df.iloc[-1]["close"])
        
        session = get_session()
        try:
            snapshot = IndicatorSnapshot(
                pair=symbol,
                fvg_detected=fvg.get("detected", False) if isinstance(fvg, dict) else bool(fvg),
                liquidity_sweep=liquidity.get("detected", False) if isinstance(liquidity, dict) else bool(liquidity),
                mss_detected=mss.get("detected", False) if isinstance(mss, dict) else bool(mss),
                unicorn_detected=unicorn.get("detected", False) if isinstance(unicorn, dict) else bool(unicorn),
                ote_low=ote_low,
                ote_mid=ote_mid,
                ote_high=ote_high,
                close_price=close_price,
                timestamp=datetime.utcnow()
            )
            session.add(snapshot)
            session.commit()
            logging.info(f"DataWarehouse: Saved indicator snapshot for {symbol}")
        except Exception as e:
            logging.error(f"DataWarehouse: Failed to save snapshot to DB: {e}")
        finally:
            session.close()
            
    except Exception as e:
        logging.error(f"DataWarehouse: Indicator calculation failed: {e}")

def export_dataset_to_csv(filepath: str = "ml_dataset.csv") -> None:
    """Exports all saved indicator snapshots to a CSV file for ML training."""
    session = get_session()
    try:
        query = session.query(IndicatorSnapshot).all()
        if not query:
            logging.warning("DataWarehouse: No snapshots found to export.")
            return
            
        data = []
        for row in query:
            data.append({
                "id": row.id,
                "timestamp": row.timestamp,
                "pair": row.pair,
                "fvg_detected": int(row.fvg_detected),
                "liquidity_sweep": int(row.liquidity_sweep),
                "mss_detected": int(row.mss_detected),
                "unicorn_detected": int(row.unicorn_detected),
                "ote_low": row.ote_low,
                "ote_mid": row.ote_mid,
                "ote_high": row.ote_high,
                "close_price": row.close_price
            })
            
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False)
        logging.info(f"DataWarehouse: Dataset successfully exported to {filepath}")
    except Exception as e:
        logging.error(f"DataWarehouse: Export failed: {e}")
    finally:
        session.close()
