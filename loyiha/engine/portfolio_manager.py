import logging
from typing import List, Dict, Any

# Fee & Slippage Constants
COMMISSION_FEE_PCT = 0.0004  # 0.04% Maker/Taker Fee per trade leg
SLIPPAGE_PCT = 0.0002        # 0.02% Slippage per execution leg


class Position:
    def __init__(self, trade_info: Dict[str, Any], leverage: float = 1.0):
        self.pair = trade_info["pair"]
        self.direction = trade_info["direction"]
        self.entry_price = trade_info["entry_price"]
        self.size = trade_info["position_size"]
        self.stop_loss = trade_info["stop_loss"]
        self.take_profit = trade_info["take_profit"]
        self.leverage = leverage

        # Calculate liquidation price (90% margin depletion trigger)
        if self.direction == "LONG":
            self.liquidation_price = self.entry_price * (1.0 - 0.9 / self.leverage)
        else:
            self.liquidation_price = self.entry_price * (1.0 + 0.9 / self.leverage)

    def current_pnl(self, current_price: float) -> float:
        """Calculate Unrealized PnL based on position size and direction."""
        diff = current_price - self.entry_price
        if self.direction == "SHORT":
            diff = -diff
        return diff * self.size


class PortfolioManager:
    def __init__(self, initial_balance: float = 50000.0, leverage: float = None):
        from config import LEVERAGE
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.leverage = leverage if leverage is not None else LEVERAGE
        self.positions: List[Position] = []
        self.trade_history: List[Dict[str, Any]] = []

    @property
    def equity(self) -> float:
        """Total balance + all unrealized PnL."""
        unrealized = sum(p.current_pnl(p.entry_price) for p in self.positions)
        return self.balance + unrealized

    def get_equity(self, current_prices: Dict[str, float]) -> float:
        unrealized = 0.0
        for p in self.positions:
            price = current_prices.get(p.pair, p.entry_price)
            unrealized += p.current_pnl(price)
        return self.balance + unrealized

    @property
    def used_margin(self) -> float:
        """Margin used by open positions."""
        total_position_value = sum(p.entry_price * p.size for p in self.positions)
        return total_position_value / self.leverage

    @property
    def free_margin(self) -> float:
        return self.equity - self.used_margin

    def add_position(self, trade_info: Dict[str, Any]) -> bool:
        """Add a new position if free margin allows."""
        new_pos = Position(trade_info, self.leverage)
        required_margin = (new_pos.entry_price * new_pos.size) / self.leverage

        if required_margin > self.free_margin:
            logging.warning(f"PortfolioManager: Insufficient margin to open {trade_info['pair']}.")
            return False

        self.positions.append(new_pos)
        logging.info(f"PortfolioManager: Opened {new_pos.direction} {new_pos.pair} at {new_pos.entry_price}.")
        return True

    def close_position(self, position: Position, exit_price: float):
        """Close a position with realistic Commission fee and Slippage deduction."""
        # Calculate Slippage adjusted exit price
        if position.direction == "LONG":
            adj_exit = exit_price * (1.0 - SLIPPAGE_PCT)
        else:
            adj_exit = exit_price * (1.0 + SLIPPAGE_PCT)

        raw_pnl = position.current_pnl(adj_exit)

        # Calculate Commission fees on entry and exit notionals
        entry_notional = position.entry_price * position.size
        exit_notional = adj_exit * position.size
        total_commission = (entry_notional + exit_notional) * COMMISSION_FEE_PCT

        net_pnl = raw_pnl - total_commission
        self.balance += net_pnl

        if position in self.positions:
            self.positions.remove(position)

        trade_record = {
            "pair": position.pair,
            "direction": position.direction,
            "entry_price": position.entry_price,
            "exit_price": adj_exit,
            "pnl": net_pnl,
            "commission": total_commission,
            "size": position.size
        }
        self.trade_history.append(trade_record)
        logging.info(f"PortfolioManager: Closed {position.pair} at {adj_exit:.2f}. Net PnL (after fees): {net_pnl:.2f}")
