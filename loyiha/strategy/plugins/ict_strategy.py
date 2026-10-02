import logging
import pandas as pd
from typing import Optional, Dict

from strategy.base import IStrategy
from strategy.combo_fixed import evaluate_ict_combo_fixed
from data.database import get_session, Signal
from config import ML_CONFIDENCE_THRESHOLD
from ml.features import extract_features
from ml.predict import predict_signal_confidence


class ICTStrategy(IStrategy):

    @property
    def name(self) -> str:
        return "ICT_ML_Strategy"

    def generate_signal(self, df: pd.DataFrame, symbol: str, df_htf: Optional[pd.DataFrame] = None) -> Optional[Dict]:
        """Process market data using ICT 6-model confluence engine and ML prediction with MTF support."""
        if df is None or df.empty or len(df) < 10:
            return None

        combo_result = evaluate_ict_combo_fixed(
            df=df,
            df_htf=df_htf,
            market_type='futures',
            require_killzone=True,
            strict_htf_alignment=True,
            symbol=symbol,
            timeframe='15m',
        )
        direction = combo_result["direction"]
        details = combo_result["details"]

        if direction not in ["LONG", "SHORT"]:
            return None

        # Extract ML features and calculate prediction confidence
        features = extract_features(df, details)

        # Predict signal confidence (ML model or rule-based fallback)
        ml_confidence = predict_signal_confidence(features, rule_confidence=combo_result["confluence_score"])

        logging.info("ML confidence for %s (%s): %.2f", symbol, direction, ml_confidence)

        if ml_confidence < ML_CONFIDENCE_THRESHOLD:
            return None

        session = get_session()
        try:
            signal = Signal(
                pair=symbol,
                direction=direction,
                confidence=round(ml_confidence * 100, 1),
                raw_message=str(details),
                source_strategy=self.name
            )
            session.add(signal)
            session.commit()
            logging.info("Signal stored in DB with id %s", signal.id)
        except Exception as e:
            logging.error("Failed to save signal to DB: %s", e)
            session.rollback()
        finally:
            session.close()

        return {
            "pair": symbol,
            "direction": direction,
            "confidence": round(ml_confidence * 100, 1),
            "details": details,
            "source_strategy": self.name
        }
