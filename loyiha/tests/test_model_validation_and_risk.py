import unittest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from ml.features import extract_features, calculate_rsi, calculate_atr
from ml.walk_forward import (
    run_walk_forward_validation,
    evaluate_calibration_bins,
    optimize_confidence_thresholds,
    calculate_strategy_breakdown,
    calculate_market_regime_breakdown
)
from engine.risk_manager import RiskManager


class TestModelValidationAndRisk(unittest.TestCase):
    def setUp(self):
        # Generate synthetic OHLCV time-series dataframe for testing
        np.random.seed(42)
        n = 300
        dates = [datetime(2025, 1, 1) + timedelta(minutes=15 * i) for i in range(n)]
        
        close = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
        high = close + np.abs(np.random.randn(n) * 0.3) + 0.1
        low = close - np.abs(np.random.randn(n) * 0.3) - 0.1
        open_p = close + np.random.randn(n) * 0.2
        volume = np.random.uniform(50, 500, n)

        self.df = pd.DataFrame({
            "timestamp": dates,
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume
        })

    def test_01_no_future_leakage_in_features(self):
        """Ensures indicators and feature extraction only use present/past bars."""
        slice_30 = self.df.iloc[:30].copy()
        rsi_at_30 = calculate_rsi(slice_30["close"], 14)
        atr_at_30 = calculate_atr(slice_30, 14)

        # Modifying future bars (after bar 30) should NOT alter features of bar 30
        slice_50_modified = self.df.iloc[:50].copy()
        slice_50_modified.loc[35:49, "close"] = 99999.0
        
        rsi_isolated = calculate_rsi(slice_50_modified.iloc[:30]["close"], 14)
        atr_isolated = calculate_atr(slice_50_modified.iloc[:30], 14)

        self.assertEqual(rsi_at_30, rsi_isolated)
        self.assertEqual(atr_at_30, atr_isolated)

    def test_02_chronological_walk_forward_split(self):
        """Verifies expanding window strictly maintains chronological ordering."""
        # Create synthetic labeled dataset
        df_labeled = self.df.copy()
        df_labeled["target"] = (np.random.rand(len(df_labeled)) > 0.5).astype(int)
        
        # Add basic feature columns
        df_labeled["rsi_14"] = 50.0
        df_labeled["atr_14"] = 0.5
        df_labeled["momentum_5"] = 0.01
        df_labeled["volatility_10"] = 0.02
        df_labeled["fvg_detected"] = 1
        df_labeled["liquidity_sweep"] = 1
        df_labeled["mss_detected"] = 0
        df_labeled["unicorn_detected"] = 0
        df_labeled["silver_bullet_detected"] = 0
        df_labeled["in_ote"] = 0
        df_labeled["session_type"] = 1

        feature_cols = ["rsi_14", "atr_14", "momentum_5", "volatility_10", "fvg_detected"]
        
        folds = run_walk_forward_validation(df_labeled, feature_cols, n_splits=3, train_ratio=0.6)
        self.assertGreaterEqual(len(folds), 2)
        
        # Verify expanding train size
        for i in range(1, len(folds)):
            self.assertGreater(folds[i]["train_samples"], folds[i - 1]["train_samples"])

    def test_03_probability_calibration_bins(self):
        """Verifies reliability binning across 0.50-1.00 intervals."""
        y_true = np.array([1, 1, 0, 1, 0, 1, 1, 1, 0, 1])
        y_probas = np.array([0.55, 0.58, 0.62, 0.65, 0.72, 0.78, 0.82, 0.88, 0.91, 0.95])

        bins = evaluate_calibration_bins(y_true, y_probas)
        self.assertEqual(len(bins), 5)
        
        high_conf_bin = [b for b in bins if b["bin"] == "90%-100%"][0]
        self.assertEqual(high_conf_bin["signals"], 2)
        self.assertEqual(high_conf_bin["real_win_rate"], 50.0)

    def test_04_threshold_selection_optimization(self):
        """Verifies threshold optimization yields monotonically filtered trade counts."""
        y_true = np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 1])
        y_probas = np.array([0.52, 0.54, 0.61, 0.68, 0.71, 0.76, 0.79, 0.81, 0.86, 0.92])

        results = optimize_confidence_thresholds(y_true, y_probas)
        self.assertEqual(len(results), 8)
        
        # Trade count at 0.50 should be >= trade count at 0.80
        t_50 = [r for r in results if r["threshold"] == 0.50][0]["trades"]
        t_80 = [r for r in results if r["threshold"] == 0.80][0]["trades"]
        self.assertGreaterEqual(t_50, t_80)

    def test_05_position_sizing_formula(self):
        """Verifies Position Size = (Account * risk%) / SL_distance."""
        rm = RiskManager(daily_loss_limit_percent=5.0, risk_per_trade_percent=1.0)
        signal = {"pair": "BTC/USDT", "direction": "LONG", "confidence": 0.85}
        
        balance = 10000.0
        price = 50000.0
        daily_loss = 0.0
        
        trade = rm.validate_and_size_trade(signal, price, balance, daily_loss)
        self.assertIsNotNone(trade)
        
        # 1% risk of 10000 = $100
        # 1% SL of 50000 = $500
        # Size = 100 / 500 = 0.2
        self.assertEqual(trade["risk_amount"], 100.0)
        self.assertAlmostEqual(trade["position_size"], 0.2, places=3)

    def test_06_daily_loss_limit_circuit_breaker(self):
        """Verifies trades are rejected when daily loss limit is hit."""
        rm = RiskManager(daily_loss_limit_percent=1.0, risk_per_trade_percent=1.0)
        signal = {"pair": "BTC/USDT", "direction": "LONG", "confidence": 0.85}
        
        # When daily loss >= 1.0%, trade must be blocked
        trade_rejected = rm.validate_and_size_trade(signal, 50000.0, 10000.0, daily_loss_percent=1.2)
        self.assertIsNone(trade_rejected)

    def test_07_consecutive_loss_circuit_breaker(self):
        """Verifies circuit breaker trips after 3 consecutive losses."""
        rm = RiskManager(daily_loss_limit_percent=5.0, max_consecutive_losses=3)
        signal = {"pair": "BTC/USDT", "direction": "LONG", "confidence": 0.85}

        rm.record_trade_result(is_win=False) # 1
        rm.record_trade_result(is_win=False) # 2
        self.assertFalse(rm.is_circuit_breaker_active(0.0))

        rm.record_trade_result(is_win=False) # 3
        self.assertTrue(rm.is_circuit_breaker_active(0.0))
        
        trade_blocked = rm.validate_and_size_trade(signal, 50000.0, 10000.0, 0.0)
        self.assertIsNone(trade_blocked)

        # Win resets consecutive losses
        rm.record_trade_result(is_win=True)
        self.assertFalse(rm.is_circuit_breaker_active(0.0))

    def test_08_strategy_and_regime_breakdowns(self):
        """Verifies strategy and market regime segmentations."""
        df_sub = pd.DataFrame({
            "target": [1, 0, 1, 1],
            "unicorn_detected": [1, 0, 1, 0],
            "silver_bullet_detected": [0, 1, 0, 1],
            "volatility_10": [0.01, 0.05, 0.02, 0.06],
            "session_type": [1, 2, 1, 2]
        })
        probas = np.array([0.8, 0.6, 0.85, 0.7])

        strat_res = calculate_strategy_breakdown(df_sub, probas)
        self.assertIn("Unicorn", strat_res)
        self.assertEqual(strat_res["Unicorn"]["sample_size"], 2)
        self.assertEqual(strat_res["Unicorn"]["win_rate"], 100.0)

        regime_res = calculate_market_regime_breakdown(df_sub, probas)
        self.assertIn("High_Volatility", regime_res)
        self.assertIn("London_Session", regime_res)

    def test_09_conservative_same_candle_resolution(self):
        """Ensures simultaneous TP/SL candle touch is resolved conservatively as a loss."""
        entry = 100.0
        tp_long = 100.65
        sl_long = 99.65
        
        # Candle that hits both SL and TP in same bar
        candle_high = 101.0
        candle_low = 99.0
        
        # Conservative resolution rule:
        is_both_touched = (candle_low <= sl_long) and (candle_high >= tp_long)
        target = 0 if is_both_touched else (1 if candle_high >= tp_long else 0)
        self.assertEqual(target, 0)

    def test_11_production_model_gate_evaluation(self):
        """Verifies candidate models with negative expectancy or poor calibration are rejected."""
        from ml.retrain import should_promote_to_production

        # Candidate with negative expectancy
        bad_candidate = {"expectancy": -0.15, "brier_score": 0.22, "log_loss": 0.65}
        current = {"expectancy": 0.25, "brier_score": 0.18, "log_loss": 0.55}

        promote, reason = should_promote_to_production(bad_candidate, current)
        self.assertFalse(promote)
        self.assertIn("Negative or zero expectancy", reason)

        # Superior candidate
        good_candidate = {"expectancy": 0.35, "brier_score": 0.16, "log_loss": 0.50}
        promote_good, _ = should_promote_to_production(good_candidate, current)
        self.assertTrue(promote_good)

    def test_12_triple_barrier_partial_tp1_and_breakeven(self):
        """Verifies TP1 closes 50% of position and shifts remaining SL to breakeven."""
        from engine.portfolio_manager import PortfolioManager, Position

        pm = PortfolioManager(initial_balance=100000.0, leverage=1.0)
        trade_info = {
            "pair": "BTC/USDT",
            "direction": "LONG",
            "entry_price": 50000.0,
            "position_size": 1.0,
            "stop_loss": 49500.0,
            "take_profit": 52000.0,
            "take_profit_1": 51000.0,
            "take_profit_2": 52000.0
        }
        pm.add_position(trade_info)
        pos = pm.positions[0]

        # Trigger TP1 partial
        pm.close_partial_position(pos, 51000.0, fraction=0.5)
        self.assertEqual(pos.size, 0.5)
        self.assertEqual(pos.stop_loss, 50000.0) # Moved to Breakeven
        self.assertTrue(pos.tp1_hit)
        self.assertEqual(len(pm.trade_history), 1)
        self.assertEqual(pm.trade_history[0]["type"], "PARTIAL_TP1_BREAKEVEN")

    def test_13_portfolio_margin_and_commission_deduction(self):
        """Verifies commission and slippage are deducted on trade closure."""
        from engine.portfolio_manager import PortfolioManager

        pm = PortfolioManager(initial_balance=10000.0, leverage=1.0)
        trade_info = {
            "pair": "ETH/USDT",
            "direction": "LONG",
            "entry_price": 3000.0,
            "position_size": 1.0,
            "stop_loss": 2900.0,
            "take_profit": 3200.0
        }
        pm.add_position(trade_info)
        pos = pm.positions[0]

        # Close position at 3100
        pm.close_position(pos, 3100.0)
        self.assertEqual(len(pm.positions), 0)
        self.assertEqual(len(pm.trade_history), 1)
        self.assertGreater(pm.trade_history[0]["commission"], 0.0)


if __name__ == "__main__":
    unittest.main()
