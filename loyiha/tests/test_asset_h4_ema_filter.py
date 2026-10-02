import unittest
import pandas as pd
import numpy as np
from strategy.combo_fixed import is_valid_signal_for_asset, ASSET_CONFIG


class TestAssetH4EMAFilter(unittest.TestCase):
    def setUp(self):
        # Create Bullish H4 candles (EMA 21 > EMA 50)
        dates = pd.date_range("2026-08-01", periods=60, freq="4h")
        self.df_h4_bullish = pd.DataFrame({
            "timestamp": dates,
            "open": [100.0 + i * 2.0 for i in range(60)],
            "high": [105.0 + i * 2.0 for i in range(60)],
            "low": [98.0 + i * 2.0 for i in range(60)],
            "close": [104.0 + i * 2.0 for i in range(60)],
            "volume": [1000.0] * 60
        })

        # Create Bearish H4 candles (EMA 21 < EMA 50)
        self.df_h4_bearish = pd.DataFrame({
            "timestamp": dates,
            "open": [300.0 - i * 2.0 for i in range(60)],
            "high": [305.0 - i * 2.0 for i in range(60)],
            "low": [295.0 - i * 2.0 for i in range(60)],
            "close": [296.0 - i * 2.0 for i in range(60)],
            "volume": [1000.0] * 60
        })

        # Create Choppy Flat H4 candles (EMA 21 ~= EMA 50)
        self.df_h4_choppy = pd.DataFrame({
            "timestamp": dates,
            "open": [200.0] * 60,
            "high": [200.5] * 60,
            "low": [199.5] * 60,
            "close": [200.0] * 60,
            "volume": [1000.0] * 60
        })

    def test_asset_timeframe_permissions(self):
        # 1. NQ/ES: ONLY H1 allowed, M15 rejected
        res_nq_15m = is_valid_signal_for_asset(symbol="NQ", timeframe="15m", direction="LONG", df_h4=self.df_h4_bullish)
        self.assertFalse(res_nq_15m["is_valid"])
        self.assertIn("TIMEFRAME_15M_NOT_ALLOWED", res_nq_15m["reject_reason"])

        res_nq_1h = is_valid_signal_for_asset(symbol="NQ", timeframe="1h", direction="LONG", df_h4=self.df_h4_bullish)
        self.assertTrue(res_nq_1h["is_valid"])

        res_es_1h = is_valid_signal_for_asset(symbol="ES", timeframe="1h", direction="LONG", df_h4=self.df_h4_bullish)
        self.assertTrue(res_es_1h["is_valid"])

        res_es_15m = is_valid_signal_for_asset(symbol="ES", timeframe="15m", direction="LONG", df_h4=self.df_h4_bullish)
        self.assertFalse(res_es_15m["is_valid"])

        # 2. CL: BOTH H1 and M15 allowed
        res_cl_15m = is_valid_signal_for_asset(symbol="CL", timeframe="15m", direction="LONG", df_h4=self.df_h4_bullish)
        self.assertTrue(res_cl_15m["is_valid"])

        res_cl_1h = is_valid_signal_for_asset(symbol="CL", timeframe="1h", direction="LONG", df_h4=self.df_h4_bullish)
        self.assertTrue(res_cl_1h["is_valid"])

        # 3. GC: ONLY M15 allowed! 1H is strictly rejected
        res_gc_15m = is_valid_signal_for_asset(symbol="GC", timeframe="15m", direction="LONG", df_h4=self.df_h4_bullish)
        self.assertTrue(res_gc_15m["is_valid"])

        res_gc_1h = is_valid_signal_for_asset(symbol="GC", timeframe="1h", direction="LONG", df_h4=self.df_h4_bullish)
        self.assertFalse(res_gc_1h["is_valid"])
        self.assertIn("TIMEFRAME_1H_NOT_ALLOWED", res_gc_1h["reject_reason"])

        # 4. YM, SI, RTY: Blacklisted (empty allowed_tfs)
        res_ym = is_valid_signal_for_asset(symbol="YM", timeframe="1h", direction="LONG", df_h4=self.df_h4_bullish)
        self.assertFalse(res_ym["is_valid"])
        self.assertIn("BLACKLISTED", res_ym["reject_reason"])

        res_si = is_valid_signal_for_asset(symbol="SI", timeframe="1h", direction="LONG", df_h4=self.df_h4_bullish)
        self.assertFalse(res_si["is_valid"])
        self.assertIn("BLACKLISTED", res_si["reject_reason"])

        res_rty = is_valid_signal_for_asset(symbol="RTY", timeframe="1h", direction="LONG", df_h4=self.df_h4_bullish)
        self.assertFalse(res_rty["is_valid"])
        self.assertIn("BLACKLISTED", res_rty["reject_reason"])

    def test_h4_ema_trend_alignment(self):
        # Bullish H4: LONG is valid, SHORT is rejected
        res_bull_long = is_valid_signal_for_asset(symbol="NQ", timeframe="1h", direction="LONG", df_h4=self.df_h4_bullish)
        self.assertTrue(res_bull_long["is_valid"])
        self.assertEqual(res_bull_long["htf_trend"], "BULLISH")

        res_bull_short = is_valid_signal_for_asset(symbol="NQ", timeframe="1h", direction="SHORT", df_h4=self.df_h4_bullish)
        self.assertFalse(res_bull_short["is_valid"])
        self.assertIn("CONTRADICTS", res_bull_short["reject_reason"])

        # Bearish H4: SHORT is valid, LONG is rejected
        res_bear_short = is_valid_signal_for_asset(symbol="NQ", timeframe="1h", direction="SHORT", df_h4=self.df_h4_bearish)
        self.assertTrue(res_bear_short["is_valid"])
        self.assertEqual(res_bear_short["htf_trend"], "BEARISH")

        res_bear_long = is_valid_signal_for_asset(symbol="NQ", timeframe="1h", direction="LONG", df_h4=self.df_h4_bearish)
        self.assertFalse(res_bear_long["is_valid"])

    def test_choppy_market_rejection(self):
        res_chop = is_valid_signal_for_asset(symbol="NQ", timeframe="1h", direction="LONG", df_h4=self.df_h4_choppy)
        self.assertFalse(res_chop["is_valid"])
        self.assertEqual(res_chop["htf_trend"], "CHOPPY")
        self.assertIn("CHOPPY", res_chop["reject_reason"])

    def test_volatility_regime_filter(self):
        # 1. Normal/Sufficient Volatility LTF data
        dates = pd.date_range("2026-08-01", periods=60, freq="1h")
        df_ltf_normal = pd.DataFrame({
            "timestamp": dates,
            "open": [100.0 + i * 0.5 for i in range(60)],
            "high": [105.0 + i * 0.5 for i in range(60)],
            "low": [95.0 + i * 0.5 for i in range(60)],
            "close": [102.0 + i * 0.5 for i in range(60)],
            "volume": [1000.0] * 60
        })

        res_normal = is_valid_signal_for_asset(
            symbol="NQ",
            timeframe="1h",
            direction="LONG",
            df_h4=self.df_h4_bullish,
            df_ltf=df_ltf_normal
        )
        self.assertTrue(res_normal["is_valid"])
        self.assertIsNone(res_normal["reject_reason"])

        # 2. Low Volatility Regime LTF data: High volatility historically, but recent candles compressed/dead
        # First 45 bars have range 10.0, last 15 bars have tiny range 0.5
        highs = [110.0 + i * 0.5 for i in range(45)] + [100.25 for _ in range(15)]
        lows = [100.0 + i * 0.5 for i in range(45)] + [99.75 for _ in range(15)]
        opens = [105.0 + i * 0.5 for i in range(45)] + [100.0 for _ in range(15)]
        closes = [106.0 + i * 0.5 for i in range(45)] + [100.1 for _ in range(15)]

        df_ltf_low_vol = pd.DataFrame({
            "timestamp": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [1000.0] * 60
        })

        res_low_vol = is_valid_signal_for_asset(
            symbol="NQ",
            timeframe="1h",
            direction="LONG",
            df_h4=self.df_h4_bullish,
            df_ltf=df_ltf_low_vol
        )
        self.assertFalse(res_low_vol["is_valid"])
        self.assertIn("LOW_VOLATILITY_REGIME", res_low_vol["reject_reason"])


if __name__ == "__main__":
    unittest.main()
