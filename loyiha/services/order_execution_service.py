"""Live Exchange Order Execution Service for Binance / Bybit Futures.

Handles actual live market/limit order placement with attached Stop Loss and Take Profit levels
when ``LIVE_TRADING_ENABLED`` environment flag is active.
"""

import os
import logging
from typing import Dict, Any, Optional

from config import (
    EXCHANGE,
    BINANCE_API_KEY,
    BINANCE_API_SECRET,
    BYBIT_API_KEY,
    BYBIT_API_SECRET,
    LEVERAGE
)

LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() in ["true", "1", "yes"]


class LiveOrderExecutionService:
    def __init__(self):
        self.enabled = LIVE_TRADING_ENABLED
        self.exchange = EXCHANGE.upper()

    def execute_live_order(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        quantity: float
    ) -> Optional[Dict[str, Any]]:
        """Place live Market Futures order with Stop Loss & Take Profit on Exchange."""
        if not self.enabled:
            logging.info("Live trading disabled (LIVE_TRADING_ENABLED=False). Skipping live exchange order execution.")
            return None

        logging.info(f"🚀 Executing LIVE {direction} order for {symbol}: qty={quantity} @ {entry_price}")

        if self.exchange == "BINANCE":
            return self._execute_binance_order(symbol, direction, entry_price, stop_loss, take_profit, quantity)
        elif self.exchange == "BYBIT":
            return self._execute_bybit_order(symbol, direction, entry_price, stop_loss, take_profit, quantity)
        else:
            logging.error(f"Unsupported live exchange: {self.exchange}")
            return None

    def _execute_binance_order(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        quantity: float
    ) -> Optional[Dict[str, Any]]:
        try:
            from binance.client import Client as BinanceClient
            if not BINANCE_API_KEY or not BINANCE_API_SECRET:
                logging.error("Binance API keys missing for live trading.")
                return None

            client = BinanceClient(BINANCE_API_KEY, BINANCE_API_SECRET)
            clean_symbol = symbol.replace("/", "").upper()

            side = "BUY" if direction.upper() == "LONG" else "SELL"
            sl_side = "SELL" if side == "BUY" else "BUY"

            # 1. Place Market Entry Order
            order = client.futures_create_order(
                symbol=clean_symbol,
                side=side,
                type="MARKET",
                quantity=quantity
            )

            # 2. Place Stop Loss Order
            client.futures_create_order(
                symbol=clean_symbol,
                side=sl_side,
                type="STOP_MARKET",
                stopPrice=round(stop_loss, 2),
                closePosition=True
            )

            # 3. Place Take Profit Order
            client.futures_create_order(
                symbol=clean_symbol,
                side=sl_side,
                type="TAKE_PROFIT_MARKET",
                stopPrice=round(take_profit, 2),
                closePosition=True
            )

            logging.info("Successfully executed Binance Futures live order for %s: %s", clean_symbol, order.get("orderId"))
            return {
                "order_id": order.get("orderId"),
                "status": "FILLED",
                "symbol": clean_symbol,
                "direction": direction,
                "entry_price": entry_price,
                "quantity": quantity
            }
        except Exception as e:
            logging.error("Failed to execute Binance live order for %s: %s", symbol, e)
            return None

    def _execute_bybit_order(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        quantity: float
    ) -> Optional[Dict[str, Any]]:
        try:
            from pybit import HTTP as BybitClient
            if not BYBIT_API_KEY or not BYBIT_API_SECRET:
                logging.error("Bybit API keys missing for live trading.")
                return None

            client = BybitClient(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
            clean_symbol = symbol.replace("/", "").upper()
            side = "Buy" if direction.upper() == "LONG" else "Sell"

            resp = client.LinearOrder.LinearOrder_new(
                symbol=clean_symbol,
                side=side,
                order_type="Market",
                qty=quantity,
                time_in_force="GoodTillCancel",
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reduce_only=False,
                close_on_trigger=False
            )

            logging.info("Successfully executed Bybit Futures live order for %s: %s", clean_symbol, resp.get("result"))
            return {
                "order_id": resp.get("result", {}).get("order_id"),
                "status": "FILLED",
                "symbol": clean_symbol,
                "direction": direction,
                "entry_price": entry_price,
                "quantity": quantity
            }
        except Exception as e:
            logging.error("Failed to execute Bybit live order for %s: %s", symbol, e)
            return None


live_order_executor = LiveOrderExecutionService()
