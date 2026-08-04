import logging
from typing import Dict, Any, Optional

class RiskManager:
    def __init__(self, daily_loss_limit_percent: float = 5.0, risk_per_trade_percent: float = 1.0):
        self.daily_loss_limit_percent = daily_loss_limit_percent
        self.risk_per_trade_percent = risk_per_trade_percent

    def validate_and_size_trade(self, signal: Dict[str, Any], current_price: float, balance: float, daily_loss_percent: float) -> Optional[Dict[str, Any]]:
        """
        Takes a raw signal and returns a structured trade order with SL, TP, and Size.
        Returns None if the trade is rejected due to risk limits.
        """
        
        # 1. Check Daily Loss Limit
        if daily_loss_percent >= self.daily_loss_limit_percent:
            logging.warning(f"RiskManager: Daily loss limit reached ({daily_loss_percent}%). Trade rejected.")
            return None
            
        direction = signal["direction"]
        
        # 2. Calculate Dynamic SL/TP (Simplified version: fixed % distance)
        # In a real system, you'd use ATR (Average True Range)
        sl_distance_percent = 0.01  # 1% move
        rr_ratio = 2.0              # 1:2 Risk to Reward
        
        if direction == "LONG":
            sl_price = current_price * (1 - sl_distance_percent)
            tp_price = current_price * (1 + (sl_distance_percent * rr_ratio))
        else:
            sl_price = current_price * (1 + sl_distance_percent)
            tp_price = current_price * (1 - (sl_distance_percent * rr_ratio))
            
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
            "take_profit": round(tp_price, 2),
            "risk_amount": round(risk_amount, 2),
            "confidence": signal["confidence"],
            "source": signal.get("source_strategy", "Unknown")
        }
        
        logging.info(f"RiskManager: Trade Validated -> Size: {trade['position_size']}, SL: {trade['stop_loss']}, TP: {trade['take_profit']}")
        return trade
        
# Global singleton
risk_manager = RiskManager()
