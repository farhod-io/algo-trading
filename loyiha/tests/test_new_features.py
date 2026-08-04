import unittest
import pandas as pd
from data.database import init_db, UserSettings, get_session
from ml.features import extract_features
from ml.tune import optimize_xgboost_params
from services.error_monitor import notify_admin_error


class TestNewFeaturesAndDatabase(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_user_settings_db_model(self):
        session = get_session()
        try:
            user = UserSettings(user_id=9999, deposit=2500.0, risk_pct=1.5, selected_symbols="GC,NQ")
            session.merge(user)
            session.commit()

            fetched = session.query(UserSettings).filter_by(user_id=9999).first()
            self.assertIsNotNone(fetched)
            self.assertEqual(fetched.deposit, 2500.0)
            self.assertEqual(fetched.risk_pct, 1.5)
        finally:
            session.close()

    def test_extract_features_extension(self):
        dates = pd.date_range(start="2026-08-04 10:00", periods=35, freq="5min")
        df = pd.DataFrame({
            "timestamp": dates,
            "open": [2600 + i for i in range(35)],
            "high": [2605 + i for i in range(35)],
            "low": [2598 + i for i in range(35)],
            "close": [2603 + i for i in range(35)],
            "volume": [100.0] * 35
        })

        indicators = {
            "fvgs": [{"gap_size": 2.5, "distance_to_price": 1.0}],
            "sweeps": [{"type": "liquidity"}],
            "mss": [{"detected": True}]
        }

        features = extract_features(df, indicators)
        self.assertIn("atr_ratio", features.columns)
        self.assertIn("trend_ema_diff", features.columns)
        self.assertIn("poc_distance", features.columns)
        self.assertIn("dist_to_session_high", features.columns)

    def test_optuna_tuning_fallback(self):
        X = pd.DataFrame({
            "fvg_detected": [1, 0, 1, 0, 1, 1],
            "close_price": [2600, 2610, 2620, 2630, 2640, 2650]
        })
        y = pd.Series([1, 0, 1, 0, 1, 1])

        params = optimize_xgboost_params(X, y, n_trials=2)
        self.assertIn("n_estimators", params)
        self.assertIn("max_depth", params)

    from unittest.mock import patch

    @patch("services.error_monitor.send_admin_alert_async")
    @patch("logging.error")
    def test_error_monitor_log(self, mock_log, mock_alert):
        err = Exception("Monitor validation check")
        notify_admin_error(err, context="Unit Test")
        self.assertTrue(mock_log.called)


if __name__ == "__main__":
    unittest.main()
