import unittest
import pandas as pd
from strategy.risk import calculate_risk
from data.database import get_user_settings_db, save_user_settings_db, init_db
from services.order_execution_service import live_order_executor


class TestAuditFixes(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_dynamic_atr_risk_calculation(self):
        dates = pd.date_range(start="2026-08-04 10:00", periods=20, freq="5min")
        df = pd.DataFrame({
            "timestamp": dates,
            "open": [2600 + i for i in range(20)],
            "high": [2608 + i for i in range(20)],
            "low": [2595 + i for i in range(20)],
            "close": [2603 + i for i in range(20)],
            "volume": [100.0] * 20
        })

        sl, tp1, tp2 = calculate_risk(entry_price=2600.0, direction="LONG", df=df, atr_mult=1.5)
        self.assertLess(sl, 2600.0)
        self.assertGreater(tp1, 2600.0)
        self.assertGreater(tp2, tp1)

    def test_user_settings_db_persistence(self):
        user_id = 77777
        saved = save_user_settings_db(user_id=user_id, deposit=15000.0, risk_pct=1.2)
        self.assertEqual(saved["deposit"], 15000.0)

        loaded = get_user_settings_db(user_id=user_id)
        self.assertEqual(loaded["deposit"], 15000.0)
        self.assertEqual(loaded["risk_pct"], 1.2)

    def test_live_order_executor_safety_guard(self):
        res = live_order_executor.execute_live_order(
            symbol="GC",
            direction="LONG",
            entry_price=2650.0,
            stop_loss=2640.0,
            take_profit=2670.0,
            quantity=1.0
        )
        # Should safely return None when LIVE_TRADING_ENABLED=False
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
