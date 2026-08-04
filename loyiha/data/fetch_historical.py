import os
import sys
import logging
import time
import pandas as pd
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.exchange_service import ExchangeFactory

def fetch_and_save_historical(symbol: str, timeframe: str, limit: int = 2000, output_path: str = None) -> str:
    """
    Fetches historical OHLCV data from the configured exchange and saves it to a CSV file.
    Perfect for generating training datasets locally without external downloads.
    """
    logging.info(f"Starting historical data fetch for {symbol} ({timeframe}), target: {limit} candles...")
    
    # We will use ccxt directly to fetch larger historical sets in loops if needed,
    # or use the default exchange service.
    # For robust bulk fetching, let's use ccxt (which is installed in requirements.txt)
    import ccxt
    
    # Determine exchange
    from config import EXCHANGE
    if EXCHANGE.upper() == "BINANCE":
        exchange = ccxt.binance({
            'enableRateLimit': True,
        })
    else:
        exchange = ccxt.bybit({
            'enableRateLimit': True,
        })
        
    all_candles = []
    since = exchange.parse8601((datetime.utcnow() - pd.Timedelta(days=180)).isoformat()) # Go back ~6 months
    
    # Fetch in loops to bypass the single-request limit (usually 500-1000)
    batch_size = 1000 if EXCHANGE.upper() == "BINANCE" else 200
    
    while len(all_candles) < limit:
        try:
            logging.info(f"Fetching batch since {exchange.iso8601(since)}...")
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=batch_size)
            if not ohlcv:
                break
            
            all_candles.extend(ohlcv)
            # Update 'since' to the timestamp of the last candle + timeframe duration in ms
            last_timestamp = ohlcv[-1][0]
            since = last_timestamp + 1
            
            # Rate limit friendly sleep
            time.sleep(exchange.rateLimit / 1000)
            
        except Exception as e:
            logging.error(f"Error fetching batch: {e}")
            break
            
    if not all_candles:
        logging.error("No candles fetched.")
        return None
        
    # Format and save
    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    # Convert ms timestamp to readable datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    
    if output_path is None:
        clean_symbol = symbol.replace("/", "_").replace("-", "_")
        output_path = f"data/historical_{clean_symbol}_{timeframe}.csv"
        
    df.to_csv(output_path, index=False)
    logging.info(f"Successfully saved {len(df)} candles to {output_path}")
    return output_path

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Example: fetch 2000 candles of BTC/USDT 15m
    symbol = "BTC/USDT"
    timeframe = "15m"
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        timeframe = sys.argv[2]
        
    fetch_and_save_historical(symbol, timeframe, limit=3000)
