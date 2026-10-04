"""Tests for the P2 quality fixes: config API persistence, dashboard auth,
unified risk formula, and config-driven Silver Bullet windows."""

import base64
import json
import os
import tempfile
import unittest

import pandas as pd

import config as config_module
import dashboard.app as dashboard_app
from engine.risk_manager import RiskManager
from strategy.risk import calculate_risk


def _basic(user: str, password: str) -> dict:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


class DashboardTestBase(unittest.TestCase):
    """Sets a known admin password and uses a temp config_local.json."""

    PASSWORD = "unit-test-pass-12345"

    def setUp(self):
        self._old_password = dashboard_app.ADMIN_PASSWORD
        dashboard_app.ADMIN_PASSWORD = self.PASSWORD
        dashboard_app.app.config["TESTING"] = True
        self.client = dashboard_app.app.test_client()

        fd, self.tmp_config = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(self.tmp_config)

        self._old_config_path = dashboard_app.CONFIG_LOCAL_PATH
        dashboard_app.CONFIG_LOCAL_PATH = self.tmp_config

        # Snapshot runtime config so tests do not leak mutations.
        self._snapshot = {
            "SYMBOLS": list(config_module.SYMBOLS),
            "SYMBOL": config_module.SYMBOL,
            "TIMEFRAME": config_module.TIMEFRAME,
            "SCAN_INTERVAL_MINUTES": config_module.SCAN_INTERVAL_MINUTES,
            "ML_CONFIDENCE_THRESHOLD": config_module.ML_CONFIDENCE_THRESHOLD,
            "LEVERAGE": config_module.LEVERAGE,
            "INITIAL_BALANCE": config_module.INITIAL_BALANCE,
        }

    def tearDown(self):
        dashboard_app.ADMIN_PASSWORD = self._old_password
        dashboard_app.CONFIG_LOCAL_PATH = self._old_config_path
        for key, value in self._snapshot.items():
            setattr(config_module, key, value)
        if os.path.exists(self.tmp_config):
            os.remove(self.tmp_config)


class TestDashboardAuth(DashboardTestBase):
    def test_index_requires_auth(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 401)

    def test_index_with_wrong_password_is_rejected(self):
        res = self.client.get("/", headers=_basic("admin", "wrong-password"))
        self.assertEqual(res.status_code, 401)

    def test_index_with_correct_password_serves_template(self):
        res = self.client.get("/", headers=_basic("admin", self.PASSWORD))
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        # Marks that dashboard/templates/index.html is actually rendered.
        self.assertIn("Control Center", body)

    def test_api_endpoints_require_auth(self):
        # GET is supported on both endpoints, so both must demand credentials.
        for path in ("/api/config", "/api/stats"):
            self.assertEqual(self.client.get(path).status_code, 401, path)

        # POST is supported on /api/config only; /api/stats is GET-only (405).
        self.assertEqual(self.client.post("/api/config").status_code, 401)
        self.assertEqual(self.client.post("/api/stats").status_code, 405)

    def test_wrong_credentials_cannot_reach_api(self):
        for path in ("/api/config", "/api/stats"):
            res = self.client.get(path, headers=_basic("admin", "nope"))
            self.assertEqual(res.status_code, 401, path)


class TestConfigPersistence(DashboardTestBase):
    def test_post_writes_config_local_json(self):
        res = self.client.post(
            "/api/config",
            json={"scan_interval_minutes": 7, "timeframe": "5m"},
            headers=_basic("admin", self.PASSWORD),
        )
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["updated"]["scan_interval_minutes"], 7)

        with open(self.tmp_config) as fh:
            saved = json.load(fh)
        self.assertEqual(saved["scan_interval_minutes"], 7)
        self.assertEqual(saved["timeframe"], "5m")

        # Applied to the running process, not just written to disk.
        self.assertEqual(config_module.SCAN_INTERVAL_MINUTES, 7)
        self.assertEqual(config_module.TIMEFRAME, "5m")

    def test_post_accepts_comma_separated_symbols(self):
        res = self.client.post(
            "/api/config",
            json={"symbols": "NQ, ES , GC"},
            headers=_basic("admin", self.PASSWORD),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(config_module.SYMBOLS, ["NQ", "ES", "GC"])
        self.assertEqual(config_module.SYMBOL, "NQ")

    def test_partial_post_preserves_existing_keys(self):
        self.client.post(
            "/api/config",
            json={"leverage": 5.0},
            headers=_basic("admin", self.PASSWORD),
        )
        self.client.post(
            "/api/config",
            json={"timeframe": "15m"},
            headers=_basic("admin", self.PASSWORD),
        )
        with open(self.tmp_config) as fh:
            saved = json.load(fh)
        self.assertEqual(saved["leverage"], 5.0)
        self.assertEqual(saved["timeframe"], "15m")

    def test_unknown_key_is_rejected(self):
        res = self.client.post(
            "/api/config",
            json={"not_a_real_key": 1},
            headers=_basic("admin", self.PASSWORD),
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["status"], "error")

    def test_out_of_range_values_are_rejected(self):
        auth = _basic("admin", self.PASSWORD)
        for body in (
            {"ml_confidence_threshold": 1.5},
            {"scan_interval_minutes": 0},
            {"leverage": 0},
            {"timeframe": "7m"},
            {"initial_balance": -1},
        ):
            res = self.client.post("/api/config", json=body, headers=auth)
            self.assertEqual(res.status_code, 400, body)

    def test_get_returns_live_config(self):
        config_module.SCAN_INTERVAL_MINUTES = 42
        res = self.client.get("/api/config", headers=_basic("admin", self.PASSWORD))
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["scan_interval_minutes"], 42)
        self.assertIn("ml_confidence_threshold", data)
        self.assertIn("leverage", data)


class TestStatsEndpoint(DashboardTestBase):
    def test_stats_returns_expected_shape(self):
        res = self.client.get("/api/stats", headers=_basic("admin", self.PASSWORD))
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        for key in (
            "balance", "total_pnl", "total_trades", "win_rate",
            "dates", "pnl_history", "open_positions",
            "recent_signals", "recent_snapshots",
        ):
            self.assertIn(key, data)
        self.assertIsInstance(data["open_positions"], list)
        self.assertIsInstance(data["recent_signals"], list)


class TestUnifiedRiskFormula(unittest.TestCase):
    """risk_manager must use the same SL/TP math as strategy.risk."""

    def test_sl_and_tp_match_strategy_risk(self):
        rm = RiskManager(daily_loss_limit_percent=100.0, risk_per_trade_percent=1.0)
        signal = {"pair": "NQ", "direction": "LONG", "confidence": 0.9}
        price, balance = 20000.0, 50000.0

        trade = rm.validate_and_size_trade(signal, price, balance, 0.0)
        self.assertIsNotNone(trade)

        sl, tp1, tp2 = calculate_risk(
            entry_price=price, direction="LONG", sl_percent=rm.sl_distance_percent
        )
        self.assertEqual(trade["stop_loss"], round(sl, 2))
        self.assertEqual(trade["take_profit_1"], round(tp1, 2))
        self.assertEqual(trade["take_profit_2"], round(tp2, 2))
        # Paper trading single TP == shared TP1 target.
        self.assertEqual(trade["take_profit"], trade["take_profit_1"])

    def test_short_sl_above_entry_and_tp_below(self):
        rm = RiskManager(daily_loss_limit_percent=100.0)
        signal = {"pair": "ES", "direction": "SHORT", "confidence": 0.9}
        trade = rm.validate_and_size_trade(signal, 5500.0, 50000.0, 0.0)
        self.assertGreater(trade["stop_loss"], 5500.0)
        self.assertLess(trade["take_profit_1"], 5500.0)
        self.assertLess(trade["take_profit_2"], trade["take_profit_1"])

    def test_position_sizing_uses_actual_sl_distance(self):
        rm = RiskManager(daily_loss_limit_percent=100.0, risk_per_trade_percent=1.0)
        signal = {"pair": "BTC/USDT", "direction": "LONG", "confidence": 0.85}
        trade = rm.validate_and_size_trade(signal, 50000.0, 10000.0, 0.0)

        self.assertEqual(trade["risk_amount"], 100.0)
        sl_distance = abs(50000.0 - trade["stop_loss"])
        self.assertAlmostEqual(
            trade["position_size"], round(100.0 / sl_distance, 4), places=4
        )

    def test_circuit_breaker_still_rejects(self):
        rm = RiskManager(daily_loss_limit_percent=1.0)
        signal = {"pair": "NQ", "direction": "LONG", "confidence": 0.9}
        self.assertIsNone(rm.validate_and_size_trade(signal, 20000.0, 50000.0, 1.5))

    def test_df_uses_atr_distance_when_supplied(self):
        rm = RiskManager(daily_loss_limit_percent=100.0)
        signal = {"pair": "NQ", "direction": "LONG", "confidence": 0.9}

        dates = pd.date_range(start="2026-08-04 10:00", periods=40, freq="5min")
        df = pd.DataFrame({
            "timestamp": dates,
            "open": [20000 + i for i in range(40)],
            "high": [20010 + i for i in range(40)],
            "low": [19995 + i for i in range(40)],
            "close": [20005 + i for i in range(40)],
            "volume": [100.0] * 40,
        })
        signal_with_df = dict(signal, df=df)

        with_df = rm.validate_and_size_trade(signal_with_df, 20050.0, 50000.0, 0.0)
        without_df = rm.validate_and_size_trade(signal, 20050.0, 50000.0, 0.0)

        self.assertIsNotNone(with_df)
        self.assertIsNotNone(without_df)
        # ATR path and percentage path must both produce a valid SL below entry.
        self.assertLess(with_df["stop_loss"], 20050.0)


class TestSilverBulletFromConfig(unittest.TestCase):
    def test_windows_are_driven_by_config(self):
        from indicators.silver_bullet import _build_windows, _to_time
        from datetime import time

        windows = _build_windows()
        self.assertEqual(len(windows), len(config_module.SILVER_BULLET_TIMES))
        for window, spec in zip(windows, config_module.SILVER_BULLET_TIMES):
            self.assertEqual(window["start"], _to_time(spec["start"], time(0, 0)))
            self.assertEqual(window["end"], _to_time(spec["end"], time(0, 0)))

    def test_default_windows_match_rule_md_killzones(self):
        """rule.md: London 03-04, NY AM 10-11, NY PM 14-15 EST == 08/15/19 UTC."""
        from indicators.silver_bullet import SILVER_BULLET_WINDOWS_UTC
        from datetime import time

        starts = [w["start"] for w in SILVER_BULLET_WINDOWS_UTC]
        self.assertEqual(starts, [time(8, 0), time(15, 0), time(19, 0)])

    def test_is_silver_bullet_time_respects_windows(self):
        import importlib
        import indicators.silver_bullet as sb

        original = list(sb.SILVER_BULLET_WINDOWS_UTC)
        sb.SILVER_BULLET_WINDOWS_UTC = [
            {"name": "Test", "start": __import__("datetime").time(10, 0),
             "end": __import__("datetime").time(11, 0)}
        ]
        try:
            self.assertIsNotNone(sb.is_silver_bullet_time(pd.Timestamp("2026-10-03 10:30:00")))
            self.assertIsNone(sb.is_silver_bullet_time(pd.Timestamp("2026-10-03 12:30:00")))
        finally:
            sb.SILVER_BULLET_WINDOWS_UTC = original

    def test_bad_config_value_falls_back(self):
        from indicators.silver_bullet import _to_time
        from datetime import time

        self.assertEqual(_to_time("not-a-time", time(8, 0)), time(8, 0))
        self.assertEqual(_to_time(None, time(15, 0)), time(15, 0))
        self.assertEqual(_to_time("19:45", time(0, 0)), time(19, 45))


if __name__ == "__main__":
    unittest.main()
