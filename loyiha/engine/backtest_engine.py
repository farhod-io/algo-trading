import logging
import pandas as pd
from typing import Dict, Any

from strategy.engine import strategy_engine
from engine.portfolio_manager import PortfolioManager
from engine.risk_manager import risk_manager


class BacktestEngine:
    def __init__(self, data: pd.DataFrame, initial_balance: float = 10000.0, leverage: float = 1.0):
        """Expects a DataFrame with historical OHLCV candles."""
        self.data = data
        self.portfolio = PortfolioManager(initial_balance, leverage)

    def generate_report(self) -> Dict[str, Any]:
        """Calculates performance metrics from the trade history."""
        trades = self.portfolio.trade_history
        total_trades = len(trades)
        if total_trades == 0:
            return {"total_trades": 0, "net_profit": 0.0, "win_rate": 0.0, "profit_factor": 0.0}

        winning_trades = [t for t in trades if t.get("pnl", 0.0) > 0]
        losing_trades = [t for t in trades if t.get("pnl", 0.0) <= 0]

        gross_profit = sum(t["pnl"] for t in winning_trades)
        gross_loss = abs(sum(t["pnl"] for t in losing_trades))

        win_rate = (len(winning_trades) / total_trades) * 100
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        net_profit = gross_profit - gross_loss

        peak = self.portfolio.initial_balance
        max_drawdown = 0.0
        current_balance = self.portfolio.initial_balance

        for t in trades:
            current_balance += t.get("pnl", 0.0)
            if current_balance > peak:
                peak = current_balance
            drawdown = (peak - current_balance) / peak * 100.0 if peak > 0 else 0.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return {
            "initial_balance": self.portfolio.initial_balance,
            "final_balance": self.portfolio.balance,
            "net_profit": round(net_profit, 2),
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_percent": round(max_drawdown, 2)
        }

    def run(self):
        """Sequential bar-by-bar backtest execution."""
        logging.info(f"Starting sequential backtest on {len(self.data)} candles...")

        window_size = 200
        if len(self.data) <= window_size:
            logging.error("Not enough data rows for backtest window.")
            return self.generate_report()

        # Iterate bar by bar sequentially without skipping
        for i in range(window_size, len(self.data)):
            window_df = self.data.iloc[i - window_size:i].copy()
            current_price = float(window_df.iloc[-1]["close"])

            # Evaluate open positions for exit with Triple Barrier & Conservative Same-Candle Resolution
            open_positions = list(self.portfolio.positions)
            for pos in open_positions:
                high = float(window_df.iloc[-1]["high"])
                low = float(window_df.iloc[-1]["low"])

                if pos.direction == "LONG":
                    # Conservative rule: Check Stop Loss first
                    if low <= pos.stop_loss:
                        self.portfolio.close_position(pos, pos.stop_loss)
                    elif not pos.tp1_hit and high >= pos.take_profit_1:
                        # Partial 50% closure at TP1, move remaining SL to breakeven
                        self.portfolio.close_partial_position(pos, pos.take_profit_1, fraction=0.5)
                        # Check if remainder reached TP2 in same bar
                        if high >= pos.take_profit_2:
                            self.portfolio.close_position(pos, pos.take_profit_2)
                    elif pos.tp1_hit and high >= pos.take_profit_2:
                        self.portfolio.close_position(pos, pos.take_profit_2)
                elif pos.direction == "SHORT":
                    # Conservative rule: Check Stop Loss first
                    if high >= pos.stop_loss:
                        self.portfolio.close_position(pos, pos.stop_loss)
                    elif not pos.tp1_hit and low <= pos.take_profit_1:
                        # Partial 50% closure at TP1, move remaining SL to breakeven
                        self.portfolio.close_partial_position(pos, pos.take_profit_1, fraction=0.5)
                        if low <= pos.take_profit_2:
                            self.portfolio.close_position(pos, pos.take_profit_2)
                    elif pos.tp1_hit and low <= pos.take_profit_2:
                        self.portfolio.close_position(pos, pos.take_profit_2)

            # Generate Signals
            signals = strategy_engine.run_all(window_df, symbol="BACKTEST")

            for signal in signals:
                validated_trade = risk_manager.validate_and_size_trade(
                    signal=signal,
                    current_price=current_price,
                    balance=self.portfolio.balance,
                    daily_loss_percent=0.0
                )

                if validated_trade:
                    self.portfolio.add_position(validated_trade)

        final_price = float(self.data.iloc[-1]["close"])
        for pos in list(self.portfolio.positions):
            self.portfolio.close_position(pos, final_price)

        logging.info(f"Backtest complete. Final balance: ${self.portfolio.balance:.2f}")

        report = self.generate_report()
        logging.info(f"Backtest Report: {report}")
        return report
