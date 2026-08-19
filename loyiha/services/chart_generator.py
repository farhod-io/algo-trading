"""Candlestick Chart Generator for Telegram Signals using Matplotlib / Mplfinance.

Annotates Fair Value Gaps (FVG), Liquidity Sweeps, Entry Price, Stop Loss, and Take Profit levels.
"""

import io
import logging
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for headless server rendering
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def generate_signal_chart(df: pd.DataFrame, signal_info: dict, max_candles: int = 50) -> io.BytesIO:
    """Generate annotated candlestick chart PNG image buffer.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV candle dataframe with columns ['open', 'high', 'low', 'close', 'timestamp']
    signal_info : dict
        Dict containing pair, direction, entry_price, sl, tp1, tp2, details

    Returns
    -------
    io.BytesIO
        PNG Image byte stream suitable for sending via Telegram send_photo.
    """
    recent = df.tail(max_candles).copy()
    recent['timestamp'] = pd.to_datetime(recent['timestamp'])

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)

    # Plot candlesticks
    for idx, row in recent.iterrows():
        t = row['timestamp']
        o, h, l, c = row['open'], row['high'], row['low'], row['close']
        color = '#26a69a' if c >= o else '#ef5350'

        # Wick
        ax.plot([t, t], [l, h], color=color, linewidth=1.2)
        # Body
        body_bottom = min(o, c)
        body_height = abs(c - o)
        if body_height == 0:
            body_height = 0.01
        ax.add_patch(plt.Rectangle(
            (mdates.date2num(t) - 0.0003, body_bottom),
            0.0006, body_height,
            facecolor=color, edgecolor=color, alpha=0.9
        ))

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    fig.autofmt_xdate()

    # Draw Signal Levels if available
    pair = signal_info.get("pair", signal_info.get("symbol", "ASSET"))
    direction = signal_info.get("direction", "LONG").upper()
    entry = signal_info.get("entry_price", signal_info.get("entry"))
    sl = signal_info.get("stop_loss", signal_info.get("sl"))
    tp1 = signal_info.get("take_profit_1", signal_info.get("tp1", signal_info.get("take_profit")))
    tp2 = signal_info.get("take_profit_2", signal_info.get("tp2"))

    last_time = recent['timestamp'].iloc[-1]
    first_time = recent['timestamp'].iloc[0]

    if entry:
        ax.axhline(y=entry, color='#29b6f6', linestyle='--', linewidth=1.5, label=f'Entry: {entry:.2f}')
    if sl:
        ax.axhline(y=sl, color='#f44336', linestyle='-', linewidth=1.5, label=f'SL: {sl:.2f}')
    if tp1:
        ax.axhline(y=tp1, color='#66bb6a', linestyle='-.', linewidth=1.2, label=f'TP1: {tp1:.2f}')
    if tp2:
        ax.axhline(y=tp2, color='#4caf50', linestyle=':', linewidth=1.5, label=f'TP2: {tp2:.2f}')

    # Highlight Fair Value Gaps (FVG) if present
    details = signal_info.get("details", {})
    fvgs = details.get("fvgs") or []
    for fvg in fvgs[:2]:
        top = fvg.get("top")
        bottom = fvg.get("bottom")
        if top and bottom:
            ax.axhspan(bottom, top, facecolor='#ffeb3b', alpha=0.25, label='FVG Zone')

    # Title & Legend
    conf = signal_info.get("confidence", 80.0)
    ax.set_title(f"⚡ ICT-ML SIGNAL: {pair} ({direction}) | Confidence: {conf}%", fontsize=12, fontweight='bold', color='#ffffff')
    ax.set_ylabel("Price", fontsize=10, color='#cccccc')
    ax.grid(True, linestyle=':', alpha=0.3)
    ax.legend(loc='upper left', facecolor='#1e1e1e', edgecolor='#333333', fontsize=8)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)

    return buf
