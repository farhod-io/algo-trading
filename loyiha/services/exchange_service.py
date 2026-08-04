import logging
import requests
from typing import Protocol, List
from datetime import datetime, timezone
import pandas as pd

from config import EXCHANGE, BINANCE_API_KEY, BINANCE_API_SECRET, BYBIT_API_KEY, BYBIT_API_SECRET

# Futures & Crypto Symbol Mapping
FUTURES_MAP = {
    "NQ": "NQ=F",
    "NQ=F": "NQ=F",
    "ES": "ES=F",
    "ES=F": "ES=F",
    "YM": "YM=F",
    "YM=F": "YM=F",
    "GC": "GC=F",
    "GC=F": "GC=F",
    "GOLD": "GC=F",
    "XAUUSD": "GC=F",
    "BTC": "BTC-USD",
    "BTCUSDT": "BTC-USD",
    "ETH": "ETH-USD",
    "ETHUSDT": "ETH-USD",
    "SOL": "SOL-USD",
    "SOLUSDT": "SOL-USD"
}


def is_market_open() -> bool:
    """Check if US Futures market is currently open.
    Futures markets are closed on Saturday and Sunday (after Friday 17:00 EST / 21:00 UTC).
    """
    now_utc = datetime.now(timezone.utc)
    weekday = now_utc.weekday()  # 0=Mon, 5=Sat, 6=Sun
    if weekday == 5:  # Saturday
        return False
    if weekday == 6 and now_utc.hour < 22:  # Sunday before 22:00 UTC
        return False
    return True


class IExchangeService(Protocol):
    def fetch_recent_candles(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Fetch OHLCV dataframe for a given symbol and timeframe."""
        pass


def normalize_crypto_symbol(symbol: str) -> str:
    """Normalize user symbol to standard Binance crypto pair (e.g. ETH -> ETHUSDT, BTC -> BTCUSDT)."""
    sym = (symbol or "").strip().upper().replace("/", "").replace("-", "")
    if sym in ["ETH", "ETHEREUM"]:
        return "ETHUSDT"
    elif sym in ["BTC", "BITCOIN"]:
        return "BTCUSDT"
    elif sym in ["SOL", "SOLANA"]:
        return "SOLUSDT"
    elif sym in ["XRP", "RIPPLE"]:
        return "XRPUSDT"
    elif not sym.endswith("USDT") and sym not in ["NQ", "NQ=F", "ES", "ES=F", "GC", "GC=F", "YM", "YM=F"]:
        return f"{sym}USDT"
    return sym


def fetch_binance_public_klines(symbol: str, timeframe: str = "5m", limit: int = 100) -> pd.DataFrame:
    """Fetch 100% real-time live OHLCV candles directly from Binance Public REST API (no keys required)."""
    clean_symbol = normalize_crypto_symbol(symbol)
    url = "https://api.binance.com/api/v3/klines"

    try:
        logging.info("Fetching real-time Binance Public candles for %s...", clean_symbol)
        resp = requests.get(url, params={"symbol": clean_symbol, "interval": timeframe, "limit": limit}, timeout=5)
        if resp.status_code == 200:
            klines = resp.json()
            if klines and isinstance(klines, list):
                df = pd.DataFrame(klines, columns=[
                    "open_time", "open", "high", "low", "close", "volume",
                    "close_time", "quote_asset_volume", "number_of_trades",
                    "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
                ])
                df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
                df = df[["open", "high", "low", "close", "volume", "timestamp"]]
                df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
                return df.reset_index(drop=True)
    except Exception as e:
        logging.warning("Binance Public REST API fetch failed for %s: %s", clean_symbol, e)

    return pd.DataFrame()


def fetch_futures_yfinance(symbol: str, timeframe: str = "5m", limit: int = 100) -> pd.DataFrame:
    """Fetch live candles for US Futures or Crypto fallback from Yahoo Finance."""
    sym_upper = symbol.upper()
    yf_symbol = FUTURES_MAP.get(sym_upper, f"{sym_upper}=F")

    try:
        import yfinance as yf
        logging.info(f"Fetching candles for {yf_symbol} via yfinance...")
        ticker = yf.Ticker(yf_symbol)
        df_raw = ticker.history(period="5d", interval=timeframe)

        if df_raw.empty:
            df_raw = ticker.history(period="7d", interval="15m")

        if df_raw.empty:
            logging.warning(f"No yfinance data returned for {yf_symbol}")
            return pd.DataFrame()

        df = df_raw.reset_index()
        df = df.rename(columns={
            "Datetime": "timestamp",
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })

        if "timestamp" not in df.columns:
            df["timestamp"] = pd.to_datetime(df.index)

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df[["open", "high", "low", "close", "volume", "timestamp"]].tail(limit)
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df.reset_index(drop=True)

    except Exception as e:
        logging.error(f"yfinance fetch error for {symbol} ({yf_symbol}): {e}")
        return pd.DataFrame()


class BinanceExchange:
    def fetch_recent_candles(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        sym_upper = symbol.upper()

        # 1. If Crypto Symbol (ETH, BTC, SOL, ETHUSDT, etc.), use Binance Public REST API
        if any(k in sym_upper for k in ["ETH", "BTC", "SOL", "USDT", "XRP", "BNB"]):
            df_crypto = fetch_binance_public_klines(symbol, timeframe, limit)
            if not df_crypto.empty:
                return df_crypto

        # 2. If US Futures (NQ, ES, YM, GC), use Yahoo Finance
        df_fut = fetch_futures_yfinance(symbol, timeframe, limit)
        if not df_fut.empty:
            return df_fut

        # 3. Fallback attempt for Binance Public REST API
        return fetch_binance_public_klines(symbol, timeframe, limit)


class BybitExchange:
    def fetch_recent_candles(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        sym_upper = symbol.upper()
        if any(k in sym_upper for k in ["ETH", "BTC", "SOL", "USDT", "XRP"]):
            df_crypto = fetch_binance_public_klines(symbol, timeframe, limit)
            if not df_crypto.empty:
                return df_crypto

        return fetch_futures_yfinance(symbol, timeframe, limit)


class ExchangeFactory:
    _instance = None

    @classmethod
    def get_exchange(cls, exchange_name: str = EXCHANGE) -> IExchangeService:
        if cls._instance is None:
            if exchange_name.upper() in ["BINANCE", "BYBIT"]:
                cls._instance = BinanceExchange()
            else:
                cls._instance = BinanceExchange()
        return cls._instance
