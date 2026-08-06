import re

sample_text = "fsoyil0v created with TradingView.com, Aug 04, 2026 07:20 UTC-4 Micro E-mini Nasdaq-100 Index Futures 1h CME O29,116.75 H29,147.00 L29,114.00 C29,128.00 +11.50 (+0.04%) USD 29,700.00 29,500.00 MNQU2026 29,128.00 49:45 29,000.00 28,900.00 28,700.00 28,600.00 28,500.00 28,380.00 28,247.00 28,136.00 28,040.00 27,940.00 27,840.00 27,740.00 27,640.00 27,545.00 18:00 30 06:00 12:00 18:00 31 06:00 12:00 Aug 3 06:00 12:00 18:00 4 06:00 12:00 18:00"

def parse_chart_info(text: str):
    txt_lower = text.lower()
    
    # 1. Symbol detection
    detected_symbol = None
    if any(k in txt_lower for k in ["mnq", "nq", "nasdaq"]):
        detected_symbol = "NQ"
    elif any(k in txt_lower for k in ["mes", "es", "s&p"]):
        detected_symbol = "ES"
    elif any(k in txt_lower for k in ["mgc", "gc", "gold", "xau"]):
        detected_symbol = "GC"
    elif any(k in txt_lower for k in ["mym", "ym", "dow"]):
        detected_symbol = "YM"
    elif any(k in txt_lower for k in ["btc", "bitcoin"]):
        detected_symbol = "BTCUSDT"

    # 2. Extract TradingView Close price C29,128.00 or C29128.00
    close_match = re.search(r"c\s*([\d,\.]+)", text, re.IGNORECASE)
    detected_price = None
    if close_match:
        try:
            val_str = close_match.group(1).replace(",", "")
            val = float(val_str)
            if val >= 100.0:
                detected_price = val
        except ValueError:
            pass

    # 3. Clean text by removing time formats like 18:00, 07:20, 49:45
    cleaned_text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", text)
    cleaned_text = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", " ", cleaned_text)

    # 4. Extract valid price numbers >= 200.0
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
        detected_price = valid_prices[0]  # Take first prominent price (e.g., top status line)

    if detected_price and not detected_symbol:
        if 1500.0 <= detected_price <= 3800.0:
            detected_symbol = "GC"
        elif 3900.0 <= detected_price <= 9000.0:
            detected_symbol = "ES"
        elif 12000.0 <= detected_price <= 35000.0:
            detected_symbol = "NQ"
        elif 35000.0 < detected_price <= 50000.0:
            detected_symbol = "YM"
        elif detected_price > 50000.0:
            detected_symbol = "BTCUSDT"

    return detected_symbol, detected_price, valid_prices

symbol, price, valid_prices = parse_chart_info(sample_text)
print("Detected Symbol:", symbol)
print("Detected Price:", price)
print("Valid Prices Sample:", valid_prices[:5])
