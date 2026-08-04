from typing import Protocol, Optional, Dict
import pandas as pd

class IStrategy(Protocol):
    """
    Interface for all trading strategies.
    Every strategy must implement the generate_signal method.
    """
    
    @property
    def name(self) -> str:
        """Name of the strategy."""
        pass
        
    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Optional[Dict]:
        """
        Process market data and possibly create a signal.
        
        Returns:
            None if no signal is found.
            Dict containing: pair, direction, confidence, details (and source_strategy)
        """
        pass
