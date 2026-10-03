"""Automated Unit Tests for ICT ML Signal System.
"""

import sys
import os
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

# Add loyiha directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indicators.fvg import detect_fvg
from indicators.liquidity import detect_liquidity_sweep
from indicators.mss import detect_mss
from indicators.orderblock import detect_orderblocks, detect_breaker_blocks
from indicators.fibonacci import calculate_ote_zone, is_price_in_ote
from indicators.unicorn import detect_unicorn
from indicators.amd import detect_amd
from indicators.silver_bullet import detect_silver_bullet
from indicators.htf_bias import determine_htf_bias
from strategy.risk import calculate_risk
from strategy.combo_fixed import evaluate_ict_combo_fixed
from ml.features import extract_features
from ml.predict import predict_signal_confidence


def generate_mock_candles(num_candles: int = 50, start_price: float = 60000.0) -> pd.DataFrame:
    """Generate mock OHLCV candle DataFrame for testing."""
    records = []
    base_time = datetime.now(timezone.utc) - timedelta(minutes=5 * num_candles)
    price = start_price

    for i in range(num_candles):
        timestamp = base_time + timedelta(minutes=5 * i)
        change = np.random.uniform(-100, 100)
        open_p = price
        close_p = price + change
        high_p = max(open_p, close_p) + np.random.uniform(10, 50)
        low_p = min(open_p, close_p) - np.random.uniform(10, 50)
        volume = np.random.uniform(10, 100)

        records.append({
            "timestamp": timestamp,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": volume
        })
        price = close_p

    return pd.DataFrame(records)


class TestIndicators(unittest.TestCase):

    def setUp(self):
        self.df = generate_mock_candles(60, start_price=68000.0)

    def test_fvg_detection(self):
        # Inject synthetic Bullish FVG (c1.high < c3.low)
        self.df.iloc[10] = {"timestamp": datetime.now(timezone.utc), "open": 68000, "high": 68100, "low": 67900, "close": 68050, "volume": 50}
        self.df.iloc[11] = {"timestamp": datetime.now(timezone.utc), "open": 68050, "high": 68500, "low": 68050, "close": 68450, "volume": 150}
        self.df.iloc[12] = {"timestamp": datetime.now(timezone.utc), "open": 68450, "high": 68700, "low": 68300, "close": 68650, "volume": 100}

        gaps = detect_fvg(self.df)
        self.assertIsInstance(gaps, list)
        if gaps:
            self.assertIn("type", gaps[0])
            self.assertIn("gap_size", gaps[0])

    def test_orderblock_detection(self):
        obs = detect_orderblocks(self.df)
        self.assertIsInstance(obs, list)

        breakers = detect_breaker_blocks(self.df)
        self.assertIsInstance(breakers, list)

    def test_liquidity_sweep(self):
        sweeps = detect_liquidity_sweep(self.df)
        self.assertIsInstance(sweeps, list)

    def test_mss_detection(self):
        shifts = detect_mss(self.df)
        self.assertIsInstance(shifts, list)

    def test_fibonacci_ote(self):
        ote_low, ote_mid, ote_high = calculate_ote_zone(self.df)
        self.assertGreater(ote_high, ote_low)
        self.assertTrue(is_price_in_ote((ote_low + ote_high) / 2.0, (ote_low, ote_mid, ote_high)))

    def test_unicorn_detection(self):
        unicorns = detect_unicorn(self.df)
        self.assertIsInstance(unicorns, list)

    def test_amd_detection(self):
        amd_res = detect_amd(self.df)
        if amd_res:
            self.assertIn("asian_high", amd_res)
            self.assertIn("current_phase", amd_res)

    def test_silver_bullet_detection(self):
        sb_res = detect_silver_bullet(self.df)
        self.assertIsInstance(sb_res, list)

    def test_htf_bias(self):
        bias_info = determine_htf_bias(self.df)
        self.assertIn(bias_info["bias"], ["BULLISH", "BEARISH", "NEUTRAL"])


class TestRiskManagement(unittest.TestCase):

    def test_long_risk_calculation(self):
        entry = 68340.0
        sl, tp1, tp2 = calculate_risk(entry_price=entry, direction="LONG", sl_percent=0.35)

        self.assertLess(sl, entry)
        self.assertGreater(tp1, entry)
        self.assertGreater(tp2, tp1)

        # SL distance = 68340 * 0.0035 = 239.19
        self.assertAlmostEqual(sl, entry - 239.19, delta=0.5)

    def test_short_risk_calculation(self):
        entry = 68340.0
        sl, tp1, tp2 = calculate_risk(entry_price=entry, direction="SHORT", sl_percent=0.35)

        self.assertGreater(sl, entry)
        self.assertLess(tp1, entry)
        self.assertLess(tp2, tp1)

    def test_lowercase_direction_handling(self):
        entry = 50000.0
        sl, tp1, tp2 = calculate_risk(entry_price=entry, direction="long", sl_percent=1.0)
        self.assertEqual(sl, 49500.0)
        self.assertEqual(tp1, 50925.0)


class TestStrategyComboAndML(unittest.TestCase):

    def setUp(self):
        self.df = generate_mock_candles(50, start_price=70000.0)

    def test_evaluate_ict_combo(self):
        combo_res = evaluate_ict_combo_fixed(self.df, market_type='futures', require_killzone=False, strict_htf_alignment=True)
        self.assertIn("direction", combo_res)
        self.assertIn("confluence_score", combo_res)

    def test_feature_extraction(self):
        combo_res = evaluate_ict_combo_fixed(self.df, market_type='futures', require_killzone=False, strict_htf_alignment=True)
        features = extract_features(self.df, combo_res["details"])

        self.assertEqual(len(features), 1)
        self.assertIn("rsi_14", features.columns)
        self.assertIn("atr_14", features.columns)
        self.assertIn("fvg_detected", features.columns)

    def test_ml_predict_fallback(self):
        combo_res = evaluate_ict_combo_fixed(self.df, market_type='futures', require_killzone=False, strict_htf_alignment=True)
        features = extract_features(self.df, combo_res["details"])
        conf = predict_signal_confidence(features, rule_confidence=0.82)
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)


if __name__ == "__main__":
    unittest.main()
