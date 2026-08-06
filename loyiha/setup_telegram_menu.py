"""Standalone script to register Telegram Bot Commands Menu on Telegram servers for Futures NQ & ES.
"""

import sys
import os
import asyncio
import logging
from telegram import Bot, BotCommand, MenuButtonCommands, BotCommandScopeDefault

# Add loyiha directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TELEGRAM_BOT_TOKEN


async def register_menu():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN .env faylida topilmadi!")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    commands = [
        BotCommand("start", "🤖 Botni ishga tushirish (NQ & ES Futures)"),
        BotCommand("status", "⚙️ NQ/ES Futures skaner holati"),
        BotCommand("chart", "📈 So'nggi NQ/ES ICT signali"),
        BotCommand("backtest", "🧪 Futures Chart va CSV backtest"),
        BotCommand("risk", "🛡 Risk $ va Kontrakt hajmini sozlash"),
        BotCommand("settings", "🔧 NQ & ES sozlamalari"),
        BotCommand("help", "❓ Qo'llanma va yordam"),
    ]

    try:
        await bot.delete_my_commands(scope=BotCommandScopeDefault())
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

        print("✅ Futures NQ & ES Telegram bot menyusi muvaffaqiyatli ro'yxatdan o'tkazildi!")
    except Exception as e:
        print(f"❌ Telegram serverida buyruqlarni o'rnatishda xatolik: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(register_menu())
