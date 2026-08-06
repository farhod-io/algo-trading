"""Utilities for fetching market data from Binance or Bybit.

We use the ExchangeFactory from services.exchange_service to abstract
the actual exchange API logic.

The functions return a ``pandas.DataFrame`` with columns:
    ['open', 'high', 'low', 'close', 'volume', 'timestamp']
"""

import time
import logging
from typing import Tuple
import pandas as pd

from config import SYMBOL, TIMEFRAME
from services.exchange_service import ExchangeFactory
from services.error_monitor import notify_admin_error


def fetch_recent_candles(symbol: str = SYMBOL, limit: int = 100, max_retries: int = 3) -> pd.DataFrame:
    """Fetch the most recent ``limit`` candles for the given symbol with exponential backoff retries.

    Returns:
        pandas.DataFrame with columns ['open', 'high', 'low', 'close', 'volume', 'timestamp']
    """
    attempt = 0
    delay = 1.0

    while attempt < max_retries:
        try:
            exchange_service = ExchangeFactory.get_exchange()
            df = exchange_service.fetch_recent_candles(symbol, TIMEFRAME, limit)

            if not df.empty:
                logging.info("Fetched %s candles for %s", len(df), symbol)
                return df
            else:
                logging.warning("Attempt %d: Empty candles returned for %s", attempt + 1, symbol)
        except Exception as e:
            logging.warning("Attempt %d failed to fetch candles for %s: %s", attempt + 1, symbol, e)
            if attempt == max_retries - 1:
                notify_admin_error(e, context=f"fetch_recent_candles({symbol})")

        attempt += 1
        if attempt < max_retries:
            time.sleep(delay)
            delay *= 2.0

    return pd.DataFrame()


def fetch_mtf_candles(symbol: str = SYMBOL, ltf: str = TIMEFRAME, htf: str = "15m", limit: int = 100) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch both LTF (e.g. 5m) and HTF (e.g. 15m) candles for MTF strategy alignment.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: (df_ltf, df_htf)
    """
    try:
        exchange_service = ExchangeFactory.get_exchange()
        df_ltf = exchange_service.fetch_recent_candles(symbol, ltf, limit)
        df_htf = exchange_service.fetch_recent_candles(symbol, htf, limit)
        return df_ltf, df_htf
    except Exception as e:
        logging.error("Failed to fetch MTF candles for %s: %s", symbol, e)
        df_ltf = fetch_recent_candles(symbol, limit)
        return df_ltf, pd.DataFrame()
