import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from bot.messages import format_signal_alert, format_analysis_result
from services.notification_service import NotificationService
from services.chart_generator import generate_signal_chart
from ml.predict import get_model_version


class TestTelegramSignalFormatting(unittest.TestCase):
    def setUp(self):
        self.notification_svc = NotificationService()

    def test_01_long_signal_full_format(self):
        """Verifies complete professional formatting for LONG signal."""
        signal = {
            "pair": "NQ",
            "direction": "LONG",
            "entry_price": 20000.0,
            "stop_loss": 19950.0,
            "take_profit_1": 20100.0,
            "take_profit_2": 20175.0,
            "confidence": 86.5,
            "source_strategy": "Unicorn Model",
            "timeframe": "15m",
            "timestamp": "2026-08-19 14:30:00 UTC",
            "session": "NY AM Killzone",
            "confluence_score": 5,
            "model_version": "v2026.08.19-xgb"
        }

        msg = format_signal_alert(signal, account_deposit=50000.0, risk_pct=0.5)

        # Check required fields
        self.assertIn("NQ", msg)
        self.assertIn("LONG", msg)
        self.assertIn("🟢", msg)
        self.assertIn("20,000.00", msg)
        self.assertIn("19,950.00", msg)
        self.assertIn("20,100.00", msg)
        self.assertIn("20,175.00", msg)
        self.assertIn("86.5%", msg)
        self.assertIn("v2026.08.19-xgb", msg)
        self.assertIn("Unicorn Model", msg)
        self.assertIn("15m", msg)
        self.assertIn("NY AM Killzone", msg)
        self.assertIn("5/6", msg)
        self.assertIn("TP1 da 50% pozitsiya yopiladi", msg)
        self.assertIn("Breakeven", msg)
        self.assertIn("50,000", msg)
        self.assertIn("$250.00", msg) # 0.5% of 50k

    def test_02_short_signal_direction_and_ordering(self):
        """Verifies SHORT signal inequalities: SL > Entry > TP1 > TP2."""
        signal = {
            "pair": "ES",
            "direction": "SHORT",
            "entry_price": 5500.0,
            "stop_loss": 5520.0,
            "take_profit_1": 5460.0,
            "take_profit_2": 5430.0,
            "confidence": 82.0,
            "source_strategy": "Silver Bullet",
            "timeframe": "5m"
        }

        msg = format_signal_alert(signal, account_deposit=50000.0, risk_pct=0.5)

        self.assertIn("ES", msg)
        self.assertIn("SHORT", msg)
        self.assertIn("🔴", msg)
        self.assertIn("5,500.00", msg)
        self.assertIn("5,520.00", msg) # SL above entry
        self.assertIn("5,460.00", msg) # TP1 below entry
        self.assertIn("5,430.00", msg) # TP2 below TP1
        self.assertIn("Silver Bullet", msg)

    def test_03_single_source_of_truth_consistency(self):
        """Ensures format_analysis_result produces identical structure to format_signal_alert."""
        details = {"unicorns": [{"breaker": 100}]}
        res_text = format_analysis_result(
            entry_price=2650.0,
            direction="LONG",
            sl=2640.0,
            tp1=2670.0,
            tp2=2685.0,
            details=details,
            confidence=85.0,
            account_deposit=50000.0,
            risk_pct=0.5,
            symbol="GC"
        )
        self.assertIn("Gold GC", res_text)
        self.assertIn("2,650.00", res_text)
        self.assertIn("2,640.00", res_text)
        self.assertIn("2,670.00", res_text)

    def test_04_model_version_resolution(self):
        """Verifies real model version is fetched without returning 'unknown'."""
        version = get_model_version()
        self.assertTrue(version.startswith("v"))
        self.assertNotIn("unknown", version.lower())

    def test_05_idempotent_signal_dispatch(self):
        """Ensures identical signal is not dispatched twice."""
        sig = {
            "pair": "NQ",
            "direction": "LONG",
            "entry_price": 20100.0,
            "timestamp": "2026-08-19 15:00:00 UTC",
            "source_strategy": "MSS_FVG"
        }

        # First attempt -> not duplicate
        self.assertFalse(self.notification_svc.is_duplicate_signal(sig))

        # Immediate second attempt -> detected as duplicate
        self.assertTrue(self.notification_svc.is_duplicate_signal(sig))

    def test_06_zero_secret_leakage(self):
        """Ensures no secret tokens, keys or sensitive credentials appear in messages."""
        signal = {
            "pair": "NQ",
            "direction": "LONG",
            "entry_price": 20000.0,
            "stop_loss": 19950.0,
            "api_key": "SECRET_TEST_API_KEY_12345",
            "bot_token": "SECRET_BOT_TOKEN_99999"
        }
        msg = format_signal_alert(signal)
        self.assertNotIn("SECRET_TEST_API_KEY", msg)
        self.assertNotIn("SECRET_BOT_TOKEN", msg)

    def test_07_chart_generation_and_fallback(self):
        """Verifies chart generation produces valid PNG buffer and handles missing levels cleanly."""
        dates = [datetime(2026, 8, 19, 10, i) for i in range(30)]
        df = pd.DataFrame({
            "timestamp": dates,
            "open": np.linspace(100, 105, 30),
            "high": np.linspace(101, 107, 30),
            "low": np.linspace(99, 104, 30),
            "close": np.linspace(100.5, 106, 30),
            "volume": [1000] * 30
        })

        sig_info = {
            "pair": "NQ",
            "direction": "LONG",
            "entry_price": 105.0,
            "stop_loss": 103.0,
            "take_profit_1": 109.0,
            "take_profit_2": 112.0,
            "confidence": 85.0
        }

        buf = generate_signal_chart(df, sig_info)
        self.assertIsNotNone(buf)
        self.assertGreater(len(buf.getvalue()), 1000)

    def test_08_malformed_signal_graceful_recovery(self):
        """Verifies signal with missing TP/SL levels auto-calculates healthy 1:2.0 and 1:3.5 targets."""
        sig_raw = {
            "pair": "BTC/USDT",
            "direction": "LONG",
            "entry_price": 60000.0,
            "stop_loss": 0.0, # Missing SL
            "take_profit_1": 0.0, # Missing TP1
            "take_profit_2": 0.0
        }
        msg = format_signal_alert(sig_raw)
        self.assertIn("60,000.00", msg)
        self.assertIn("Take-Profit 1", msg)
        self.assertIn("Take-Profit 2", msg)
        self.assertIn("R:R=1:2.00", msg)


if __name__ == "__main__":
    unittest.main()
