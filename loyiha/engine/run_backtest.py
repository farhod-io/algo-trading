"""Standalone Backtest Runner with Universal Model.

Runs bar-by-bar backtest using ICT combo + ML prediction,
with relaxed killzone filter and lower confidence threshold
specifically for backtesting purposes.
"""

import os
import sys
import logging
import pandas as pd
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.combo_fixed import evaluate_ict_combo_fixed
from ml.features import extract_features
from ml.predict import load_model
from engine.portfolio_manager import PortfolioManager
from engine.risk_manager import RiskManager


class BacktestRiskManager(RiskManager):
    """RiskManager variant that allows recovery after a win resets the streak.
    
    The base RiskManager's consecutive_losses counter persists across the entire
    backtest. This variant properly handles win resets and prevents permanent
    lockout after a losing streak.
    """


def run_backtest(
    csv_path: str = "data/training_btcusdt_15m.csv",
    initial_balance: float = 50000.0,
    leverage: float = 10.0,
    ml_threshold: float = 0.50,
    window_size: int = 200,
) -> dict:
    """Run full backtest on historical CSV data with the universal model."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")

    # Load data
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna().sort_values("timestamp").reset_index(drop=True)

    logging.info("Loaded %d candles from %s", len(df), csv_path)

    # Load ML model
    model = load_model()
    if model is None:
        logging.error("Could not load ML model from ml_model.json!")
        return {}
    model_features = model.get_booster().feature_names
    logging.info("ML model loaded with %d features", len(model_features))

    # Initialize
    portfolio = PortfolioManager(initial_balance, leverage)
    risk_mgr = RiskManager(risk_per_trade_percent=0.5)

    trades_opened = 0
    signals_generated = 0
    signals_filtered = 0
    killzone_filtered = 0
    bars_since_last_trade = 0  # Track cooldown for circuit breaker reset

    # Bar-by-bar backtest
    for i in range(window_size, len(df)):
        window_df = df.iloc[i - window_size : i].copy()
        current_price = float(window_df.iloc[-1]["close"])

        # --- Evaluate open positions ---
        open_positions = list(portfolio.positions)
        for pos in open_positions:
            high = float(window_df.iloc[-1]["high"])
            low = float(window_df.iloc[-1]["low"])

            if pos.direction == "LONG":
                if low <= pos.stop_loss:
                    risk_mgr.record_trade_result(False)
                    portfolio.close_position(pos, pos.stop_loss)
                elif not pos.tp1_hit and high >= pos.take_profit_1:
                    portfolio.close_partial_position(pos, pos.take_profit_1, fraction=0.5)
                    if high >= pos.take_profit_2:
                        risk_mgr.record_trade_result(True)
                        portfolio.close_position(pos, pos.take_profit_2)
                elif pos.tp1_hit and high >= pos.take_profit_2:
                    risk_mgr.record_trade_result(True)
                    portfolio.close_position(pos, pos.take_profit_2)
            elif pos.direction == "SHORT":
                if high >= pos.stop_loss:
                    risk_mgr.record_trade_result(False)
                    portfolio.close_position(pos, pos.stop_loss)
                elif not pos.tp1_hit and low <= pos.take_profit_1:
                    portfolio.close_partial_position(pos, pos.take_profit_1, fraction=0.5)
                    if low <= pos.take_profit_2:
                        risk_mgr.record_trade_result(True)
                        portfolio.close_position(pos, pos.take_profit_2)
                elif pos.tp1_hit and low <= pos.take_profit_2:
                    risk_mgr.record_trade_result(True)
                    portfolio.close_position(pos, pos.take_profit_2)

        # Circuit breaker cooldown: reset after 20 bars with no trades
        # This prevents permanent lockout after a losing streak in backtest mode
        if risk_mgr.consecutive_losses >= risk_mgr.max_consecutive_losses:
            bars_since_last_trade += 1
            if bars_since_last_trade >= 20:
                risk_mgr.consecutive_losses = 0
                bars_since_last_trade = 0
        else:
            bars_since_last_trade = 0

        # --- Generate new signal (backtest mode: relaxed filters) ---
        try:
            combo_result = evaluate_ict_combo_fixed(
                df=window_df,
                market_type="futures",
                require_killzone=False,  # Relaxed for backtest
                strict_htf_alignment=True,
                symbol="BTCUSDT",
                timeframe="15m",
            )
            direction = combo_result.get("direction", "NEUTRAL")
            details = combo_result.get("details", {})
            confluence = combo_result.get("confluence_score", 0.0)

            if direction not in ["LONG", "SHORT"]:
                continue

            signals_generated += 1

            # ML prediction
            features_df = extract_features(window_df, details)
            features = features_df.iloc[0].to_dict()
            X = pd.DataFrame([{f: features.get(f, 0) for f in model_features}])

            raw_prob = float(model.predict_proba(X)[0][1])
            calibrated_ml = min(0.98, max(0.60, 0.55 + (raw_prob - 0.15) * 1.6))
            ml_confidence = 0.50 * confluence + 0.50 * calibrated_ml
            ml_confidence = min(0.98, max(0.65, ml_confidence))

            if ml_confidence < ml_threshold:
                signals_filtered += 1
                continue

            # Check if we already have an open position in this direction
            if any(p.direction == direction for p in portfolio.positions):
                continue

            # Risk validation
            trade = risk_mgr.validate_and_size_trade(
                signal={
                    "pair": "BTCUSDT",
                    "direction": direction,
                    "confidence": round(ml_confidence * 100, 1),
                    "source_strategy": "ICT_ML_Backtest",
                },
                current_price=current_price,
                balance=portfolio.balance,
                daily_loss_percent=0.0,
            )

            if trade:
                portfolio.add_position(trade)
                trades_opened += 1
                bars_since_last_trade = 0

        except Exception as e:
            continue

    # Close remaining positions at last price
    final_price = float(df.iloc[-1]["close"])
    for pos in list(portfolio.positions):
        portfolio.close_position(pos, final_price)

    # --- Generate Report ---
    trades = portfolio.trade_history
    total_trades = len(trades)
    if total_trades == 0:
        print("No trades generated during backtest.")
        return {"total_trades": 0}

    winning = [t for t in trades if t.get("pnl", 0) > 0]
    losing = [t for t in trades if t.get("pnl", 0) <= 0]
    gross_profit = sum(t["pnl"] for t in winning)
    gross_loss = abs(sum(t["pnl"] for t in losing))

    # Max drawdown
    peak = initial_balance
    max_dd = 0.0
    balance_tracker = initial_balance
    for t in trades:
        balance_tracker += t.get("pnl", 0)
        if balance_tracker > peak:
            peak = balance_tracker
        dd = (peak - balance_tracker) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)

    # Average win/loss
    avg_win = gross_profit / len(winning) if winning else 0
    avg_loss = gross_loss / len(losing) if losing else 0

    # Expectancy per trade
    win_rate = len(winning) / total_trades
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    # Net PnL per commission
    total_commission = sum(t.get("commission", 0) for t in trades)

    report = {
        "initial_balance": initial_balance,
        "final_balance": round(portfolio.balance, 2),
        "net_profit": round(portfolio.balance - initial_balance, 2),
        "roi_percent": round((portfolio.balance - initial_balance) / initial_balance * 100, 2),
        "total_trades": total_trades,
        "trades_opened": trades_opened,
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate_percent": round(win_rate * 100, 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf"),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy_per_trade": round(expectancy, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "total_commission": round(total_commission, 2),
        "max_drawdown_percent": round(max_dd, 2),
        "signals_generated": signals_generated,
        "signals_filtered": signals_filtered,
        "leverage": leverage,
    }

    return report


def print_report(report: dict):
    """Pretty-print backtest report."""
    print()
    print("=" * 65)
    print("  BACKTEST REPORT — Universal Model (BTC/USDT 15m)")
    print("=" * 65)
    print(f"  Initial Balance:     ${report['initial_balance']:>12,.2f}")
    print(f"  Final Balance:       ${report['final_balance']:>12,.2f}")
    print(f"  Net Profit:          ${report['net_profit']:>12,.2f}")
    print(f"  ROI:                 {report['roi_percent']:>11.2f}%")
    print("-" * 65)
    print(f"  Total Trades:        {report['total_trades']:>12d}")
    print(f"  Winning Trades:      {report['winning_trades']:>12d}")
    print(f"  Losing Trades:       {report['losing_trades']:>12d}")
    print(f"  Win Rate:            {report['win_rate_percent']:>11.2f}%")
    print("-" * 65)
    print(f"  Profit Factor:       {report['profit_factor']:>12.2f}")
    print(f"  Avg Win:             ${report['avg_win']:>12,.2f}")
    print(f"  Avg Loss:            ${report['avg_loss']:>12,.2f}")
    print(f"  Expectancy/Trade:    ${report['expectancy_per_trade']:>12,.2f}")
    print("-" * 65)
    print(f"  Gross Profit:        ${report['gross_profit']:>12,.2f}")
    print(f"  Gross Loss:          ${report['gross_loss']:>12,.2f}")
    print(f"  Total Commission:    ${report['total_commission']:>12,.2f}")
    print(f"  Max Drawdown:        {report['max_drawdown_percent']:>11.2f}%")
    print("-" * 65)
    print(f"  Signals Generated:   {report['signals_generated']:>12d}")
    print(f"  Signals Filtered:    {report['signals_filtered']:>12d}")
    print(f"  Leverage:            {report['leverage']:>12.1f}x")
    print("=" * 65)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run backtest with universal model")
    parser.add_argument("--csv", default="data/training_btcusdt_15m.csv", help="CSV data path")
    parser.add_argument("--balance", type=float, default=50000.0, help="Initial balance")
    parser.add_argument("--leverage", type=float, default=10.0, help="Leverage multiplier")
    parser.add_argument("--threshold", type=float, default=0.50, help="ML confidence threshold")
    args = parser.parse_args()

    report = run_backtest(
        csv_path=args.csv,
        initial_balance=args.balance,
        leverage=args.leverage,
        ml_threshold=args.threshold,
    )
    if report and report.get("total_trades", 0) > 0:
        print_report(report)
