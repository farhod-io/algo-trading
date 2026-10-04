"""Flask Web Dashboard & API with HTTP Basic Authentication for system configuration, scanning, and retraining.

Routes
------
- ``GET  /``             HTML control panel (auth required)
- ``GET  /api/config``   Read current runtime configuration
- ``POST /api/config``   Persist configuration to ``config_local.json``
- ``GET  /api/stats``    Paper-trading / signal / snapshot statistics
- ``POST /api/scan``     Trigger a market scan
- ``POST /api/retrain``  Trigger ML model retraining
"""

import json
import os
import sys
import logging
from functools import wraps
from datetime import datetime, timedelta, timezone

from flask import Flask, request, jsonify, render_template

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as config_module
from config import (
    SYMBOLS,
    TIMEFRAME,
    SCAN_INTERVAL_MINUTES,
    ML_CONFIDENCE_THRESHOLD,
    INITIAL_BALANCE,
    DEFAULT_RISK_PCT,
    LEVERAGE,
    DATABASE_URL,
    CONFIG_LOCAL_PATH,
)

app = Flask(__name__)

# Basic Auth Credentials from environment.
# SECURITY: no default password. If ADMIN_PASSWORD is unset/empty every
# authenticated request is denied instead of falling back to a known value.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD") or "").strip()

if not ADMIN_PASSWORD:
    logging.warning(
        "ADMIN_PASSWORD is not set -- dashboard API will reject all logins. "
        "Set ADMIN_PASSWORD in .env before using the dashboard."
    )

# Keys accepted by POST /api/config and persisted to config_local.json.
# Mirrors the overrides read at import time in config.py.
_ALLOWED_CONFIG_KEYS = {
    "symbols",
    "timeframe",
    "ml_confidence_threshold",
    "scan_interval_minutes",
    "leverage",
    "initial_balance",
}


def check_auth(username, password):
    if not ADMIN_PASSWORD:
        return False
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return jsonify({"error": "Unauthorized. HTTP Basic Auth required."}), 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}
        return f(*args, **kwargs)
    return decorated


@app.route("/", methods=["GET"])
@requires_auth
def index():
    """Serve the control panel from dashboard/templates/index.html."""
    return render_template("index.html")


def _current_config() -> dict:
    """Live view of runtime config (module attrs, so config_local overrides show)."""
    return {
        "symbols": list(config_module.SYMBOLS),
        "timeframe": config_module.TIMEFRAME,
        "scan_interval_minutes": int(config_module.SCAN_INTERVAL_MINUTES),
        "ml_confidence_threshold": float(config_module.ML_CONFIDENCE_THRESHOLD),
        "leverage": float(config_module.LEVERAGE),
        "initial_balance": float(config_module.INITIAL_BALANCE),
        "default_risk_pct": float(config_module.DEFAULT_RISK_PCT),
        "database_url": DATABASE_URL,
    }


def _coerce(key: str, value):
    """Validate/coerce an incoming value for the shape config.py expects."""
    if key == "symbols":
        if isinstance(value, str):
            value = [s.strip() for s in value.split(",") if s.strip()]
        if not isinstance(value, list) or not value:
            raise ValueError("symbols must be a non-empty list or comma-separated string")
        return [str(s) for s in value]
    if key == "timeframe":
        value = str(value)
        if value not in {"1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"}:
            raise ValueError(f"unsupported timeframe: {value}")
        return value
    if key == "ml_confidence_threshold":
        v = float(value)
        if not 0.0 <= v <= 1.0:
            raise ValueError("ml_confidence_threshold must be between 0 and 1")
        return v
    if key in ("scan_interval_minutes",):
        v = int(value)
        if v < 1:
            raise ValueError("scan_interval_minutes must be >= 1")
        return v
    if key == "leverage":
        v = float(value)
        if v < 1:
            raise ValueError("leverage must be >= 1")
        return v
    if key == "initial_balance":
        v = float(value)
        if v <= 0:
            raise ValueError("initial_balance must be > 0")
        return v
    return value


@app.route("/api/config", methods=["GET", "POST"])
@requires_auth
def config_api():
    if request.method == "POST":
        data = request.json or {}
        unknown = set(data) - _ALLOWED_CONFIG_KEYS
        if unknown:
            return jsonify({"status": "error", "message": f"unknown keys: {sorted(unknown)}"}), 400

        cleaned = {}
        for key, value in data.items():
            try:
                cleaned[key] = _coerce(key, value)
            except (TypeError, ValueError) as exc:
                return jsonify({"status": "error", "message": f"{key}: {exc}"}), 400

        # Merge onto existing local overrides so a partial POST keeps other keys.
        existing = {}
        if os.path.exists(CONFIG_LOCAL_PATH):
            try:
                with open(CONFIG_LOCAL_PATH, "r") as fh:
                    existing = json.load(fh)
            except (OSError, ValueError) as exc:
                logging.warning("Could not read existing config_local.json: %s", exc)
                existing = {}

        existing.update(cleaned)
        try:
            with open(CONFIG_LOCAL_PATH, "w") as fh:
                json.dump(existing, fh, indent=2, sort_keys=True)
        except OSError as exc:
            return jsonify({"status": "error", "message": f"write failed: {exc}"}), 500

        # Apply to this process immediately; a restart picks it up too.
        _apply_runtime_config(existing)
        return jsonify({"status": "success", "updated": cleaned, "config": _current_config()})

    return jsonify(_current_config())


def _apply_runtime_config(local_cfg: dict) -> None:
    """Push config_local.json values onto the running config module."""
    try:
        if "symbols" in local_cfg and local_cfg["symbols"]:
            config_module.SYMBOLS = list(local_cfg["symbols"])
            config_module.SYMBOL = config_module.SYMBOLS[0]
        if "timeframe" in local_cfg:
            config_module.TIMEFRAME = str(local_cfg["timeframe"])
        if "ml_confidence_threshold" in local_cfg:
            config_module.ML_CONFIDENCE_THRESHOLD = float(local_cfg["ml_confidence_threshold"])
        if "scan_interval_minutes" in local_cfg:
            config_module.SCAN_INTERVAL_MINUTES = int(local_cfg["scan_interval_minutes"])
        if "leverage" in local_cfg:
            config_module.LEVERAGE = float(local_cfg["leverage"])
        if "initial_balance" in local_cfg:
            config_module.INITIAL_BALANCE = float(local_cfg["initial_balance"])
    except (TypeError, ValueError, KeyError) as exc:
        logging.error("Failed applying runtime config: %s", exc)


@app.route("/api/stats", methods=["GET"])
@requires_auth
def stats_api():
    """Statistics consumed by dashboard/templates/index.html."""
    from data.database import get_session, PaperTrade, Signal, IndicatorSnapshot

    session = get_session()
    try:
        closed = session.query(PaperTrade).filter(
            PaperTrade.status.in_(["CLOSED", "LIQUIDATED"])
        ).order_by(PaperTrade.closed_at.asc()).all()
        open_trades = session.query(PaperTrade).filter(PaperTrade.status == "OPEN").all()

        total_pnl = sum(t.pnl for t in closed if t.pnl)
        wins = sum(1 for t in closed if t.pnl and t.pnl > 0)
        total_trades = len(closed)
        win_rate = (wins / total_trades) * 100.0 if total_trades else 0.0

        # Equity curve: cumulative PnL by close date.
        dates, running, pnl_history = [], float(config_module.INITIAL_BALANCE), []
        for t in closed:
            running += float(t.pnl or 0.0)
            when = t.closed_at or t.created_at
            dates.append(when.strftime("%Y-%m-%d %H:%M") if when else "")
            pnl_history.append(round(running, 2))

        signals = (
            session.query(Signal)
            .order_by(Signal.timestamp.desc())
            .limit(25)
            .all()
        )
        snapshots = (
            session.query(IndicatorSnapshot)
            .order_by(IndicatorSnapshot.timestamp.desc())
            .limit(25)
            .all()
        )

        return jsonify({
            "balance": round(running, 2),
            "total_pnl": round(total_pnl, 2),
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "dates": dates,
            "pnl_history": pnl_history,
            "open_positions": [
                {
                    "pair": t.pair,
                    "direction": t.direction,
                    "entry_price": float(t.entry_price or 0.0),
                    "stop_loss": float(t.stop_loss or 0.0),
                    "take_profit": float(t.take_profit or 0.0),
                    "size": float(t.position_size or 0.0),
                }
                for t in open_trades
            ],
            "recent_signals": [
                {
                    "pair": s.pair,
                    "direction": s.direction,
                    "confidence": float(s.confidence or 0.0),
                    "strategy": s.source_strategy or "-",
                    "timestamp": s.timestamp.strftime("%Y-%m-%d %H:%M") if s.timestamp else "",
                }
                for s in signals
            ],
            "recent_snapshots": [
                {
                    "pair": sn.pair,
                    "timestamp": sn.timestamp.strftime("%Y-%m-%d %H:%M") if sn.timestamp else "",
                    "close_price": float(sn.close_price or 0.0),
                    "fvg": bool(sn.fvg_detected),
                    "sweep": bool(sn.liquidity_sweep),
                    "mss": bool(sn.mss_detected),
                }
                for sn in snapshots
            ],
        })
    finally:
        session.close()


@app.route("/api/scan", methods=["POST"])
@requires_auth
def trigger_scan():
    try:
        from scheduler.scanner import scan_market
        scan_market()
        return jsonify({"status": "success", "message": "Market scan triggered."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/retrain", methods=["POST"])
@requires_auth
def trigger_retrain():
    try:
        from ml.train_universal_model import train_universal_model
        train_universal_model()
        return jsonify({"status": "success", "message": "Model retraining triggered."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
