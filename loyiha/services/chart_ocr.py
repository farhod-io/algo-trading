"""OCR and Image Analysis Service for Reading Trading Charts.

Extracts text, numbers, symbol names (Gold GC, NQ, ES, YM, BTC),
and exact price levels directly from uploaded chart screenshot pixels using EasyOCR & RegEx.
"""

import os
import re
import logging
import warnings
from typing import Dict, Any, Optional

# Suppress PyTorch MPS pin_memory UserWarning on macOS
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*pin_memory.*")

ocr_reader_instance = None


def get_ocr_reader():
    global ocr_reader_instance
    if ocr_reader_instance is None:
        try:
            import easyocr
            ocr_reader_instance = easyocr.Reader(['en'], gpu=False)
        except Exception as e:
            logging.warning("EasyOCR initialization note: %s", e)
            return None
    return ocr_reader_instance


def extract_chart_info_from_image(image_path: str) -> Dict[str, Any]:
    """Read uploaded chart image pixels and extract symbol, entry price, and metadata.

    Returns:
        dict: {"symbol": str, "detected_price": Optional[float], "raw_text": str}
    """
    if not os.path.exists(image_path):
        return {"symbol": "NQ", "detected_price": None, "raw_text": ""}

    detected_text = ""
    detected_price = None
    detected_symbol = None

    reader = get_ocr_reader()
    if reader is not None:
        try:
            results = reader.readtext(image_path, detail=0)
            detected_text = " ".join(results)
            logging.info("OCR extracted text from chart: %s", detected_text[:300])
        except Exception as e:
            logging.error("OCR execution error: %s", e)

    txt_lower = detected_text.lower()

    # 1. Symbol keyword detection from TradingView header or chart text
    if any(k in txt_lower for k in ["mnq", "nq", "nasdaq"]):
        detected_symbol = "NQ"
    elif any(k in txt_lower for k in ["mes", "es", "s&p", "sp500"]):
        detected_symbol = "ES"
    elif any(k in txt_lower for k in ["mgc", "gc", "gold", "xau"]):
        detected_symbol = "GC"
    elif any(k in txt_lower for k in ["mym", "ym", "dow", "djia"]):
        detected_symbol = "YM"
    elif any(k in txt_lower for k in ["btc", "bitcoin"]):
        detected_symbol = "BTCUSDT"

    # 2. Extract TradingView Close price: C29,128.00 or C29128.00 or C 29,128.00
    close_match = re.search(r"c\s*([\d,\.]+)", detected_text, re.IGNORECASE)
    if close_match:
        try:
            val_str = close_match.group(1).replace(",", "")
            val = float(val_str)
            if val >= 100.0:
                detected_price = val
        except ValueError:
            pass

    # 3. Filter out time formats (18:00, 12:00, 07:20, 49:45) and dates (08/04/2026)
    cleaned_text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", detected_text)
    cleaned_text = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", " ", cleaned_text)

    # 4. Extract valid financial price numbers >= 200.0
    tokens = re.findall(r"[\d,]+\.\d+|\b\d{4,6}\b", cleaned_text)
    valid_prices = []
    for tok in tokens:
        try:
            v = float(tok.replace(",", ""))
            if 200.0 <= v <= 200000.0:
                valid_prices.append(v)
        except ValueError:
            pass

    if not detected_price and valid_prices:
        # Prioritize prices that match financial market ranges
        for p in valid_prices:
            if (1500.0 <= p <= 3800.0) or (3900.0 <= p <= 9000.0) or (12000.0 <= p <= 35000.0) or (p > 50000.0):
                detected_price = p
                break
        if not detected_price:
            detected_price = valid_prices[0]

    # 5. Price range symbol auto-inference if symbol was not explicitly in header text
    if detected_price and not detected_symbol:
        if 1500.0 <= detected_price <= 3800.0:
            detected_symbol = "GC"
        elif 3900.0 <= detected_price <= 9000.0:
            detected_symbol = "ES"
        elif detected_price >= 9000.0:
            detected_symbol = "NQ"

    return {
        "symbol": detected_symbol,
        "detected_price": detected_price,
        "raw_text": detected_text
    }
