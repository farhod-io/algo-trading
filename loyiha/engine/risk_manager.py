import logging
from typing import Dict, Any, Optional

class RiskManager:
    def __init__(
        self,
        daily_loss_limit_percent: float = 1.0,
        risk_per_trade_percent: float = 1.0,
        max_consecutive_losses: int = 3
    ):
        self.daily_loss_limit_percent = daily_loss_limit_percent
        self.risk_per_trade_percent = risk_per_trade_percent
        self.max_consecutive_losses = max_consecutive_losses
        self.consecutive_losses = 0

    def record_trade_result(self, is_win: bool) -> None:
        """Updates consecutive loss state upon trade closure."""
        if is_win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            logging.warning(
                f"RiskManager: Loss recorded. Consecutive losses: {self.consecutive_losses}/{self.max_consecutive_losses}"
            )

    def is_circuit_breaker_active(self, daily_loss_percent: float) -> bool:
        """Evaluates both daily drawdown and consecutive loss limits."""
        if daily_loss_percent >= self.daily_loss_limit_percent:
            return True
        if self.consecutive_losses >= self.max_consecutive_losses:
            return True
        return False

    def validate_and_size_trade(
        self,
        signal: Dict[str, Any],
        current_price: float,
        balance: float,
        daily_loss_percent: float
    ) -> Optional[Dict[str, Any]]:
        """
        Takes a raw signal and returns a structured trade order with SL, TP, and Size.
        Returns None if the trade is rejected due to risk limits.
        """
        # 1. Check Circuit Breaker (Daily Loss or Consecutive Losses)
        if self.is_circuit_breaker_active(daily_loss_percent):
            reason = (
                f"Daily loss limit reached ({daily_loss_percent}% >= {self.daily_loss_limit_percent}%)"
                if daily_loss_percent >= self.daily_loss_limit_percent
                else f"Consecutive loss limit reached ({self.consecutive_losses} >= {self.max_consecutive_losses})"
            )
            logging.warning(f"RiskManager Circuit Breaker Tripped: {reason}. Trade rejected.")
            return None
            
        direction = signal["direction"]
        
        # 2. Calculate Dynamic SL/TP1/TP2
        sl_distance_percent = 0.01  # 1% move
        rr_ratio_1 = 2.0            # 1:2 Risk to Reward for TP1 (partial close)
        rr_ratio_2 = 3.5            # 1:3.5 Risk to Reward for TP2 (full close)
        
        if direction == "LONG":
            sl_price = current_price * (1 - sl_distance_percent)
            tp1_price = current_price * (1 + (sl_distance_percent * rr_ratio_1))
            tp2_price = current_price * (1 + (sl_distance_percent * rr_ratio_2))
        else:
            sl_price = current_price * (1 + sl_distance_percent)
            tp1_price = current_price * (1 - (sl_distance_percent * rr_ratio_1))
            tp2_price = current_price * (1 - (sl_distance_percent * rr_ratio_2))
            
        sl_distance_abs = abs(current_price - sl_price)
        
        # 3. Position Sizing
        # Risk Amount = Balance * (Risk% / 100)
        # Position Size = Risk Amount / SL Distance (Absolute)
        risk_amount = balance * (self.risk_per_trade_percent / 100.0)
        position_size = risk_amount / sl_distance_abs if sl_distance_abs > 0 else 0
        
        trade = {
            "pair": signal["pair"],
            "direction": direction,
            "entry_price": current_price,
            "position_size": round(position_size, 4),
            "stop_loss": round(sl_price, 2),
            "take_profit": round(tp1_price, 2),
            "take_profit_1": round(tp1_price, 2),
            "take_profit_2": round(tp2_price, 2),
            "risk_amount": round(risk_amount, 2),
            "confidence": signal["confidence"],
            "source": signal.get("source_strategy", "Unknown")
        }
        
        logging.info(f"RiskManager: Trade Validated -> Size: {trade['position_size']}, SL: {trade['stop_loss']}, TP1: {trade['take_profit_1']}, TP2: {trade['take_profit_2']}")
        return trade
        
# Global singleton
risk_manager = RiskManager()
