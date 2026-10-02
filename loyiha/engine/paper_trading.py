import logging
from typing import Dict, Any
from datetime import datetime, timezone

from events.event_bus import event_bus
from data.database import get_session, PaperTrade
from services.exchange_service import ExchangeFactory
from config import TIMEFRAME, INITIAL_BALANCE, LEVERAGE
from engine.risk_manager import risk_manager


class PaperTradingEngine:
    def __init__(self):
        event_bus.subscribe("SIGNAL_GENERATED", self.on_signal_generated)

    def _calculate_current_balance_and_daily_loss(self, session) -> tuple:
        """Calculate real current paper balance and today's loss percentage from DB."""
        initial_balance = INITIAL_BALANCE

        closed_trades = session.query(PaperTrade).filter(
            PaperTrade.status.in_(["CLOSED", "LIQUIDATED"])
        ).all()

        total_pnl = sum(t.pnl for t in closed_trades if t.pnl)
        current_balance = max(100.0, initial_balance + total_pnl)

        # Calculate today's loss
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_trades = session.query(PaperTrade).filter(
            PaperTrade.closed_at >= today_start,
            PaperTrade.status.in_(["CLOSED", "LIQUIDATED"])
        ).all()

        today_loss = sum(abs(t.pnl) for t in today_trades if t.pnl and t.pnl < 0)
        daily_loss_percent = (today_loss / current_balance) * 100.0 if current_balance > 0 else 0.0

        return current_balance, daily_loss_percent

    def _manage_open_trades(self, session, symbol: str, current_price: float):
        """Check open trades for SL/TP/Liquidation hits and close them."""
        open_trades = session.query(PaperTrade).filter(
            PaperTrade.pair == symbol,
            PaperTrade.status == "OPEN"
        ).all()

        for trade in open_trades:
            hit = False
            liquidated = False
            pnl = 0.0

            leverage = LEVERAGE
            # Apply 0.04% maker/taker fee + 0.02% slippage simulation
            fee_rate = 0.0006
            trade_value = trade.entry_price * trade.position_size
            fee_cost = trade_value * fee_rate * 2.0  # entry + exit fee

            if trade.direction == "LONG":
                liq_price = trade.entry_price * (1.0 - 0.9 / leverage)
                if current_price <= liq_price:
                    liquidated = True
                    pnl = - (trade.entry_price * trade.position_size) / leverage - fee_cost
                elif current_price <= trade.stop_loss:
                    hit = True
                    pnl = (trade.stop_loss - trade.entry_price) * trade.position_size - fee_cost
                elif current_price >= trade.take_profit:
                    hit = True
                    pnl = (trade.take_profit - trade.entry_price) * trade.position_size - fee_cost
            else:  # SHORT
                liq_price = trade.entry_price * (1.0 + 0.9 / leverage)
                if current_price >= liq_price:
                    liquidated = True
                    pnl = - (trade.entry_price * trade.position_size) / leverage - fee_cost
                elif current_price >= trade.stop_loss:
                    hit = True
                    pnl = (trade.entry_price - trade.stop_loss) * trade.position_size - fee_cost
                elif current_price <= trade.take_profit:
                    hit = True
                    pnl = (trade.entry_price - trade.take_profit) * trade.position_size - fee_cost

            if liquidated:
                trade.status = "LIQUIDATED"
                trade.exit_price = current_price
                trade.pnl = pnl
                trade.closed_at = datetime.now(timezone.utc)
                logging.warning(f"💥 PaperTrade LIQUIDATED: {trade.direction} {trade.pair} exit: {current_price}, PnL: {pnl:.2f}")
            elif hit:
                trade.status = "CLOSED"
                trade.exit_price = current_price
                trade.pnl = pnl
                trade.closed_at = datetime.now(timezone.utc)
                logging.info(f"PaperTrade Closed: {trade.direction} {trade.pair} exit: {current_price}, PnL: {pnl:.2f}")

    def on_signal_generated(self, signal: Dict[str, Any]):
        symbol = signal.get("pair")
        direction = signal.get("direction")

        exchange_service = ExchangeFactory.get_exchange()
        df = exchange_service.fetch_recent_candles(symbol, TIMEFRAME, limit=1)
        if df.empty:
            logging.error(f"PaperTrading: Could not fetch entry price for {symbol}")
            return

        current_price = float(df.iloc[-1]["close"])

        session = get_session()
        try:
            self._manage_open_trades(session, symbol, current_price)
            session.commit()

            balance, daily_loss_pct = self._calculate_current_balance_and_daily_loss(session)

            validated_trade = risk_manager.validate_and_size_trade(
                signal=signal,
                current_price=current_price,
                balance=balance,
                daily_loss_percent=daily_loss_pct
            )

            if validated_trade:
                trade = PaperTrade(
                    pair=symbol,
                    direction=direction,
                    entry_price=current_price,
                    stop_loss=validated_trade["stop_loss"],
                    take_profit=validated_trade["take_profit"],
                    position_size=validated_trade["position_size"],
                    status="OPEN",
                    created_at=datetime.now(timezone.utc)
                )
                session.add(trade)
                session.commit()
                logging.info(f"PaperTrade Opened: {direction} {symbol} size: {trade.position_size} @ {current_price}")
            else:
                trade = PaperTrade(
                    pair=symbol,
                    direction=direction,
                    entry_price=current_price,
                    status="REJECTED",
                    reject_reason="RiskManager rejected or sizing limits reached",
                    created_at=datetime.now(timezone.utc)
                )
                session.add(trade)
                session.commit()
                logging.info(f"PaperTrade Rejected by RiskManager: {symbol}")

        except Exception as e:
            session.rollback()
            logging.error(f"PaperTrading Execution Error: {e}")
        finally:
            session.close()


paper_trading_engine = PaperTradingEngine()
