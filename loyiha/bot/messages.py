"""Telegram message formatting utilities for ICT-ML Futures & Market Signal Bot (NQ, ES, Gold GC, YM, BTC).
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from services.exchange_service import is_market_open
from ml.predict import get_model_version


def format_signal_alert(signal: Dict[str, Any], account_deposit: float = 50000.0, risk_pct: float = 0.5) -> str:
    """Format professional, full-detail alert message when a new futures signal is detected."""
    symbol = signal.get("pair", signal.get("symbol", "NQ"))
    direction = signal.get("direction", "LONG").upper()
    confidence = float(signal.get("confidence", 80.0))
    timestamp = signal.get("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
    timeframe = signal.get("timeframe", "15m")
    strategy_name = signal.get("source_strategy", signal.get("strategy", "ICT Confluence"))
    model_version = signal.get("model_version") or get_model_version()

    entry_price = float(signal.get("entry_price", signal.get("entry", 0.0)))
    sl = float(signal.get("stop_loss", signal.get("sl", 0.0)))
    tp1 = float(signal.get("take_profit_1", signal.get("tp1", signal.get("take_profit", 0.0))))
    tp2 = float(signal.get("take_profit_2", signal.get("tp2", 0.0)))

    # Direction-specific safety validation & fallback
    if entry_price > 0:
        sl_pts = abs(entry_price - sl) if sl > 0 else entry_price * 0.0035
        if direction == "LONG":
            sl = entry_price - sl_pts
            tp1 = entry_price + (sl_pts * 2.0) if tp1 <= 0 or tp1 <= entry_price else tp1
            tp2 = entry_price + (sl_pts * 3.5) if tp2 <= 0 or tp2 <= tp1 else tp2
        else:
            sl = entry_price + sl_pts
            tp1 = entry_price - (sl_pts * 2.0) if tp1 <= 0 or tp1 >= entry_price else tp1
            tp2 = entry_price - (sl_pts * 3.5) if tp2 <= 0 or tp2 >= tp1 else tp2
    else:
        sl_pts = 0.0

    sl_pct = (sl_pts / entry_price * 100.0) if entry_price > 0 else 0.35
    tp1_pts = abs(tp1 - entry_price) if entry_price > 0 else sl_pts * 2.0
    tp2_pts = abs(tp2 - entry_price) if entry_price > 0 else sl_pts * 3.5
    tp1_pct = (tp1_pts / entry_price * 100.0) if entry_price > 0 else 0.70
    tp2_pct = (tp2_pts / entry_price * 100.0) if entry_price > 0 else 1.25

    rrr1 = (tp1_pts / sl_pts) if sl_pts > 0 else 2.00
    rrr2 = (tp2_pts / sl_pts) if sl_pts > 0 else 3.50

    # Risk & Contract Math
    dollar_risk = account_deposit * (risk_pct / 100.0)

    sym_upper = symbol.upper()
    if "GC" in sym_upper or "GOLD" in sym_upper or "XAU" in sym_upper:
        emini_pt_val, micro_pt_val = 100.0, 10.0
        contract_name = "Gold GC (Gold Futures)"
        micro_label = "MGC (Micro Gold)"
        emini_label = "GC (Gold Futures)"
    elif "ES" in sym_upper:
        emini_pt_val, micro_pt_val = 50.0, 5.0
        contract_name = "ES (S&P 500 Futures)"
        micro_label = "MES (Micro S&P)"
        emini_label = "ES (E-mini S&P)"
    elif "YM" in sym_upper or "DOW" in sym_upper:
        emini_pt_val, micro_pt_val = 5.0, 0.50
        contract_name = "YM (Dow Jones Futures)"
        micro_label = "MYM (Micro Dow)"
        emini_label = "YM (E-mini Dow)"
    elif "BTC" in sym_upper:
        emini_pt_val, micro_pt_val = 1.0, 1.0
        contract_name = "BTC/USDT"
        micro_label = "Lots"
        emini_label = "Position"
    else:  # Default NQ
        emini_pt_val, micro_pt_val = 20.0, 2.0
        contract_name = "NQ (Nasdaq-100 Futures)"
        micro_label = "MNQ (Micro Nasdaq)"
        emini_label = "NQ (E-mini Nasdaq)"

    micro_contracts = (dollar_risk / (sl_pts * micro_pt_val)) if (sl_pts > 0) else 0.0
    emini_contracts = (dollar_risk / (sl_pts * emini_pt_val)) if (sl_pts > 0) else 0.0

    icon = "🟢" if direction == "LONG" else "🔴"
    session_label = signal.get("session", "NY AM Killzone" if "14:" in str(timestamp) or "15:" in str(timestamp) else "Active Market")
    confluence_score = signal.get("confluence_score", 4)

    # Market open / weekend notice
    market_notice = ""
    if not is_market_open():
        market_notice = "\n⚠️ *BOZOR YOPIQ (Dam olish kuni)* — Juma kungi yopilish narxlari bo'yicha tahlil\n"

    return (
        f"🔔 YANGI SAVDO SIGNALI {icon}\n"
        f"{market_notice}"
        f"• Aktiv: **{symbol}** ({contract_name})\n"
        f"• Yo'nalish: **{direction}** {icon}\n"
        f"• Timeframe: **{timeframe}** | Sessiya: **{session_label}**\n"
        f"• Strategiya: **{strategy_name}** (Confluence: {confluence_score}/6)\n"
        f"• Model Versiyasi: `{model_version}`\n"
        f"• AI Ishonch Koeffitsiyenti: **{confidence:.1f}%**\n\n"
        f"🎯 BUYURTMA DARAJALARI:\n"
        f"• Kirish (Entry): **{entry_price:,.2f}**\n"
        f"• Stop-Loss (SL): **{sl:,.2f}** ({sl_pts:.2f} pts / -{sl_pct:.2f}%)\n"
        f"• Take-Profit 1: **{tp1:,.2f}** ({tp1_pts:.2f} pts / +{tp1_pct:.2f}%, R:R=1:{rrr1:.2f})\n"
        f"  └ *Qoida: TP1 da 50% pozitsiya yopiladi va Stop Loss Breakeven ({entry_price:,.2f}) ga suriladi.*\n"
        f"• Take-Profit 2: **{tp2:,.2f}** ({tp2_pts:.2f} pts / +{tp2_pct:.2f}%, R:R=1:{rrr2:.2f})\n"
        f"  └ *Qoida: Qolgan 50% pozitsiya to'liq yopiladi.*\n\n"
        f"🛡 RISK VA POZITSIYA HAJMI:\n"
        f"• Hisob: ${account_deposit:,.0f} | Risk: {risk_pct}% (Maks. zarar: ${dollar_risk:,.2f})\n"
        f"• Micro Kontraktlar ({micro_label}): **{micro_contracts:.2f} ta**\n"
        f"• E-mini Kontraktlar ({emini_label}): **{emini_contracts:.2f} ta**\n\n"
        f"🕒 Signal Vaqti: `{timestamp}`"
    )


def format_analysis_result(
    entry_price: float,
    direction: str,
    sl: float,
    tp1: float,
    tp2: float,
    details: Dict[str, Any],
    confidence: float,
    account_deposit: float = 50000.0,
    risk_pct: float = 0.5,
    symbol: str = "NQ"
) -> str:
    """Format detailed futures/market analysis result including contract points, risk amount and lot/contract sizing."""
    signal_dict = {
        "pair": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss": sl,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
        "confidence": confidence,
        "details": details
    }
    return format_signal_alert(signal_dict, account_deposit=account_deposit, risk_pct=risk_pct)


def format_backtest_guide() -> str:
    """Return instructions for chart backtesting mode."""
    return (
        "🧪 BACKTESTING & CHART TAHLIL REJIMI (Gold, NQ, ES, YM, BTC)\n\n"
        "Toza chart rasmi yoki narxi yuklanganda bot uni ICT modellari va ML bo'yicha tahlil qiladi:\n\n"
        "📍 Qanday foydalaniladi:\n"
        "1. Gold, NQ, ES, YM chart rasmini yuboring (rasm ostida `Gold`, `NQ`, `ES` deb belgilashingiz mumkin).\n"
        "2. Yoki joriy narxni yozib yuboring (masalan: `2650.50`).\n"
        "3. Yoki CSV fayl ko'rinishida tarixiy shamlarni yuklang.\n\n"
        "💡 Bot avtomatik tarzda:\n"
        "✅ Entry nuqtasi\n"
        "✅ Stop-Loss & Take-Profit 1/2 darajalari (Points & %)\n"
        "✅ Aniq Risk miqdori ($ va % da)\n"
        "✅ Micro va E-mini kontraktlar sonini hisoblab beradi!"
    )

