import unittest
from unittest.mock import patch

import services.error_monitor as error_monitor
from data.database import init_db, get_scanner_state, set_scanner_state
from scheduler.scanner import _load_last_alerted, _remember_alerted, last_alerted_candle


class TestAlertCooldown(unittest.TestCase):
    """P1 #8: a repeating error must not flood the admin chat."""

    def setUp(self):
        error_monitor.reset_alert_cooldown()

    def tearDown(self):
        error_monitor.reset_alert_cooldown()

    @patch("services.error_monitor.send_admin_alert_async")
    @patch("logging.error")
    def test_repeat_error_sends_only_once_within_cooldown(self, mock_log, mock_send):
        ctx = "cooldown-unit-test"

        error_monitor.notify_admin_error(Exception("boom 1"), context=ctx)
        error_monitor.notify_admin_error(Exception("boom 2"), context=ctx)
        error_monitor.notify_admin_error(Exception("boom 3"), context=ctx)

        # First dispatches, the rest are rate-limited.
        self.assertEqual(mock_send.call_count, 1)
        # Every occurrence is still logged, nothing is swallowed.
        self.assertEqual(mock_log.call_count, 3)

    @patch("services.error_monitor.send_admin_alert_async")
    def test_different_contexts_do_not_block_each_other(self, mock_send):
        error_monitor.notify_admin_error(Exception("a"), context="ctx-a")
        error_monitor.notify_admin_error(Exception("b"), context="ctx-b")
        self.assertEqual(mock_send.call_count, 2)

    @patch("services.error_monitor.send_admin_alert_async")
    def test_cooldown_expiry_allows_next_alert(self, mock_send):
        ctx = "ctx-expiry"
        error_monitor.notify_admin_error(Exception("first"), context=ctx)
        error_monitor.reset_alert_cooldown(ctx)
        error_monitor.notify_admin_error(Exception("second"), context=ctx)
        self.assertEqual(mock_send.call_count, 2)


class TestPersistentDeduplication(unittest.TestCase):
    """P1 #9: dedup state must survive a process restart (memory -> DB)."""

    def setUp(self):
        init_db()
        last_alerted_candle.clear()

    def tearDown(self):
        last_alerted_candle.clear()

    def test_state_roundtrips_through_db(self):
        set_scanner_state("unit:probe", "2026-10-03 12:00:00")
        self.assertEqual(get_scanner_state("unit:probe"), "2026-10-03 12:00:00")
        set_scanner_state("unit:probe", "2026-10-03 12:15:00")
        self.assertEqual(get_scanner_state("unit:probe"), "2026-10-03 12:15:00")

    def test_missing_key_returns_none(self):
        self.assertIsNone(get_scanner_state("unit:definitely-missing"))

    def test_dedup_survives_memory_clear(self):
        """Simulates a restart: in-memory cache wiped, DB retains the value."""
        _remember_alerted("NQ", "LONG", "candle-abc")

        last_alerted_candle.clear()  # simulated restart

        self.assertEqual(_load_last_alerted("NQ", "LONG"), "candle-abc")
        # First read re-warms the memory cache.
        self.assertIn(("NQ", "LONG"), last_alerted_candle)

    def test_new_candle_is_not_suppressed(self):
        _remember_alerted("ES", "SHORT", "candle-1")
        self.assertEqual(_load_last_alerted("ES", "SHORT"), "candle-1")
        _remember_alerted("ES", "SHORT", "candle-2")
        self.assertEqual(_load_last_alerted("ES", "SHORT"), "candle-2")

    def test_symbols_and_directions_are_independent(self):
        _remember_alerted("NQ", "LONG", "shared-candle")
        self.assertIsNone(_load_last_alerted("NQ", "SHORT"))
        self.assertIsNone(_load_last_alerted("GC", "LONG"))


class TestMarketOpenGate(unittest.TestCase):
    """P1 #5: scanning must stop when the futures market is closed."""

    @patch("scheduler.scanner.is_market_open", return_value=False)
    @patch("scheduler.scanner.fetch_mtf_candles")
    @patch("scheduler.scanner.init_db")
    def test_scan_skips_when_market_closed(self, mock_init, mock_fetch, mock_open):
        from scheduler.scanner import scan_market

        scan_market()

        mock_open.assert_called_once()
        # No data fetch and no DB init should happen on a closed market.
        mock_fetch.assert_not_called()
        mock_init.assert_not_called()

    @patch("scheduler.scanner.is_market_open", return_value=True)
    @patch("scheduler.scanner.init_db")
    def test_scan_proceeds_when_market_open(self, mock_init, mock_open):
        from scheduler.scanner import scan_market

        scan_market()  # fetch_mtf_candles returns empty frames -> loop no-ops

        mock_open.assert_called_once()
        mock_init.assert_called_once()


class TestDashboardAuth(unittest.TestCase):
    """P1 #6: no hardcoded default password."""

    @patch.dict("os.environ", {"ADMIN_PASSWORD": ""})
    def test_missing_password_denies_everything(self):
        import importlib

        import dashboard.app as app_mod

        importlib.reload(app_mod)
        try:
            self.assertEqual(app_mod.ADMIN_PASSWORD, "")
            self.assertFalse(app_mod.check_auth("admin", ""))
            self.assertFalse(app_mod.check_auth("admin", "antigravity2026"))
            self.assertFalse(app_mod.check_auth("admin", "any-password"))
        finally:
            importlib.reload(app_mod)  # restore real env-driven config

    @patch.dict("os.environ", {"ADMIN_PASSWORD": "s3cure-test-pass"})
    def test_configured_password_is_honoured(self):
        import importlib

        import dashboard.app as app_mod

        importlib.reload(app_mod)
        try:
            self.assertEqual(app_mod.ADMIN_PASSWORD, "s3cure-test-pass")
            self.assertTrue(app_mod.check_auth("admin", "s3cure-test-pass"))
            self.assertFalse(app_mod.check_auth("admin", "wrong"))
            self.assertFalse(app_mod.check_auth("wronguser", "s3cure-test-pass"))
        finally:
            importlib.reload(app_mod)

    def test_no_hardcoded_default_in_source(self):
        import inspect

        import dashboard.app as app_mod

        src = inspect.getsource(app_mod)
        self.assertNotIn("antigravity2026", src)


if __name__ == "__main__":
    unittest.main()
