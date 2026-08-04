import unittest
import pandas as pd
from indicators.htf_bias import determine_htf_bias
from strategy.combo import evaluate_ict_combo
from data.market_data import fetch_mtf_candles


class TestMTFAlignment(unittest.TestCase):
    def test_determine_htf_bias(self):
        dates = pd.date_range(start="2026-08-04 08:00", periods=30, freq="15min")
        df_htf_bullish = pd.DataFrame({
            "timestamp": dates,
            "open": [2600 + i * 2 for i in range(30)],
            "high": [2605 + i * 2 for i in range(30)],
            "low": [2598 + i * 2 for i in range(30)],
            "close": [2604 + i * 2 for i in range(30)],
            "volume": [100.0] * 30
        })

        res = determine_htf_bias(df_htf_bullish)
        self.assertEqual(res["bias"], "BULLISH")

    def test_strict_htf_filtering(self):
        dates_ltf = pd.date_range(start="2026-08-04 10:00", periods=20, freq="5min")
        df_ltf = pd.DataFrame({
            "timestamp": dates_ltf,
            "open": [2650 - i for i in range(20)],
            "high": [2652 - i for i in range(20)],
            "low": [2648 - i for i in range(20)],
            "close": [2649 - i for i in range(20)],
            "volume": [100.0] * 20
        })

        dates_htf = pd.date_range(start="2026-08-04 08:00", periods=30, freq="15min")
        df_htf_bullish = pd.DataFrame({
            "timestamp": dates_htf,
            "open": [2600 + i * 2 for i in range(30)],
            "high": [2605 + i * 2 for i in range(30)],
            "low": [2598 + i * 2 for i in range(30)],
            "close": [2604 + i * 2 for i in range(30)],
            "volume": [100.0] * 30
        })

        combo_res = evaluate_ict_combo(df_ltf, df_htf=df_htf_bullish)
        # Counter-trend SHORT signal should be filtered to NEUTRAL
        self.assertNotEqual(combo_res["direction"], "SHORT")


if __name__ == "__main__":
    unittest.main()
