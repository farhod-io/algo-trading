"""ICT Strategy Combination Engine — Legacy Wrapper.

This module now delegates to combo_fixed.py which contains the full implementation
with market type support, killzone filters, HTF alignment, and asset validation.

All callers should migrate to importing from strategy.combo_fixed directly.
"""

from typing import Dict, Any, Optional
import pandas as pd

from strategy.combo_fixed import (
    evaluate_ict_combo_fixed,
    is_in_trading_killzone,
    ASSET_CONFIG,
    is_valid_signal_for_asset,
)


def evaluate_ict_combo(df: pd.DataFrame, df_htf: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Evaluate all 6 ICT models — delegates to combo_fixed with sensible defaults.

    Parameters
    ----------
    df : pd.DataFrame
        LTF Candle data
    df_htf : pd.DataFrame, optional
        HTF Candle data for MTF bias alignment

    Returns
    -------
    Dict[str, Any]
        Confluence assessment dictionary (same shape as combo_fixed output)
    """
    return evaluate_ict_combo_fixed(
        df=df,
        df_htf=df_htf,
        market_type='futures',
        require_killzone=False,      # Legacy: no killzone filter (combo.py didn't have one)
        strict_htf_alignment=True,
        symbol=None,
        timeframe=None,
    )
