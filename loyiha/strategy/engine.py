import logging
import pandas as pd
from typing import List, Dict, Optional

from strategy.base import IStrategy
from strategy.plugins.ict_strategy import ICTStrategy

class StrategyEngine:
    """
    Manages all loaded strategy plugins.
    Iterates over them to generate signals for a given market snapshot.
    """
    def __init__(self):
        self.strategies: List[IStrategy] = [
            ICTStrategy()
            # More strategies can be added here dynamically or statically
        ]
        logging.info(f"StrategyEngine initialized with {len(self.strategies)} strategies.")

    def run_all(self, df: pd.DataFrame, symbol: str, df_htf: Optional[pd.DataFrame] = None) -> List[Dict]:
        """
        Runs all registered strategies.
        Returns a list of generated signals.
        """
        signals = []
        for strategy in self.strategies:
            try:
                sig = strategy.generate_signal(df, symbol, df_htf=df_htf)
                if sig:
                    signals.append(sig)
            except Exception as e:
                logging.error(f"Error running strategy {strategy.name} for {symbol}: {e}")
                
        return signals

# Global singleton engine
strategy_engine = StrategyEngine()
