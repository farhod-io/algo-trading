"""Flask Web Dashboard & API with HTTP Basic Authentication for system configuration, scanning, and retraining.
"""

import os
import sys
import logging
from functools import wraps
from flask import Flask, request, jsonify, render_template_string

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    SYMBOLS,
    TIMEFRAME,
    SCAN_INTERVAL_MINUTES,
    ML_CONFIDENCE_THRESHOLD,
    INITIAL_BALANCE,
    DEFAULT_RISK_PCT,
    DATABASE_URL
)

app = Flask(__name__)

# Basic Auth Credentials from environment
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not ADMIN_PASSWORD:
    logging.warning("ADMIN_PASSWORD not set in environment! Using default development credentials.")
    ADMIN_PASSWORD = "antigravity2026"


def check_auth(username, password):
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

def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>ICT-ML Trading Dashboard</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
            .card { background: #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }
            h1 { color: #38bdf8; }
            .badge { background: #0284c7; padding: 4px 12px; border-radius: 9999px; font-size: 14px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🤖 ICT-ML Futures Trading System</h1>
            <p>Status: <span class="badge">Faol 🟢</span></p>
            <p><strong>Aktivlar:</strong> {{ symbols }}</p>
            <p><strong>Timeframe:</strong> {{ timeframe }}</p>
            <p><strong>Scan Interval:</strong> {{ scan_interval }} min</p>
            <p><strong>AI Threshold:</strong> {{ threshold }}%</p>
            <p><strong>Prop Firm Deposit:</strong> ${{ deposit }} | Risk: {{ risk }}%</p>
        </div>
    </body>
    </html>
    """, symbols=", ".join(SYMBOLS), timeframe=TIMEFRAME, scan_interval=SCAN_INTERVAL_MINUTES, threshold=int(ML_CONFIDENCE_THRESHOLD*100), deposit=f"{INITIAL_BALANCE:,.0f}", risk=DEFAULT_RISK_PCT)


@app.route("/api/config", methods=["GET", "POST"])
@requires_auth
def config_api():
    if request.method == "POST":
        data = request.json or {}
        return jsonify({"status": "success", "updated": data})
    return jsonify({
        "symbols": SYMBOLS,
        "timeframe": TIMEFRAME,
        "scan_interval": SCAN_INTERVAL_MINUTES,
        "ml_threshold": ML_CONFIDENCE_THRESHOLD,
        "initial_balance": INITIAL_BALANCE,
        "default_risk_pct": DEFAULT_RISK_PCT
    })


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
    app.run(host="0.0.0.0", port=5000)
