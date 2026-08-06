Men ICT (Inner Circle Trader) metodologiyasiga asoslangan, ML (Machine Learning) 
yordamida signallarni filtrlaydigan va Telegram orqali xabar beradigan SAVDO 
SIGNAL TIZIMI yasamoqchiman.

MUHIM: Bu tizim HECH QACHON avtomatik savdo ochmaydi. U faqat SIGNAL va TAHLL 
beradi. Men buyurtmani o‘zim brokerda qo‘lda ochaman.

--- LOYIHANING ASOSIY TALABLARI ---

1. TIL: Python 3.10+
2. INTERFEYS: Telegram Bot (signal va tahlil xabarlari shu yerga keladi)
3. MA'LUMOTLAR MANBAI: Binance yoki Bybit API (real-time narxlar)
4. ASOSIY VAZIFA: 
   - Har 5-15 daqiqada bozorni skanerlab, ICT modellari asosida potensial 
     kirish nuqtalarini topish
   - ML modeli (XGBoost) yordamida har bir signalga ishonch foizi (confidence) 
     berish
   - Signal topilganda menga Telegram orqali xabar yuborish
   - Men signalga javoban hozirgi narxni yozib yuborsam, aniq Entry, Stop-Loss,
     Take-Profit va batafsil tahlil qaytarish

--- ICT MODELLAR (TIZIM ANIQLASHI KERAK) ---

Quyidagi 6 ta ICT modelini to‘liq implementatsiya qil:

1. ICT 2022 Mentorship Model:
   - Liquidity Sweep (Oldingi High/Low yoki Equal Highs/Lows ni yutib yuborish)
   - Displacement (keskin teskari harakat)
   - MSS (Market Structure Shift — oxirgi Swing High yoki Swing Low buzilishi)
   - FVG (Fair Value Gap — 3 shamdan iborat nomutanosiblik zonasi)

2. Silver Bullet Model:
   - Faqat 3 ta vaqt oralig‘ida ishlaydi (EST vaqtida):
     * 03:00 – 04:00 (London sessiyasi)
     * 10:00 – 11:00 (NY ertalab)
     * 14:00 – 15:00 (NY tushdan keyin)
   - Bu vaqt oralig‘ida likvidlik sweep + kamida 1 kadrli FVG hosil bo‘lishi kerak

3. Power of 3 (AMD — Accumulation, Manipulation, Distribution):
   - Accumulation: Osiyo sessiyasida tor diapazon
   - Manipulation: London ochilishida soxta breakout (liquidity sweep)
   - Distribution: NY sessiyasida haqiqiy yo‘nalishdagi harakat

4. OTE (Optimal Trade Entry):
   - Fibonachchi 0.618, 0.705 va 0.786 darajalari orasidagi zona
   - FVG aynan shu zonaga to‘g‘ri kelishi kerak

5. Unicorn Model:
   - Breaker Block + FVG bir xil zonada ustma-ust tushishi
   - Eng yuqori ehtimolli signal

6. MMBM / MMSM (Market Maker Buy/Sell Model):
   - Institutsional yo‘nalishni tasdiqlash
   - HTF (Higher Timeframe) bias bilan mos kelishi kerak

--- ML MODEL (XGBoost) ---

1. Feature Engineering:
   Har bir signal uchun quyidagi xususiyatlarni hisobla:
   - FVG kattaligi, yoshi, narxga masofa
   - Order Block kuchi
   - Liquidity Sweep deteksiyoni (ha/yo‘q)
   - Kun soati, sessiya turi
   - RSI, ATR, hajm kabi texnik ko‘rsatkichlar
   - OTE zonasiga moslik (0-1 oralig‘ida)

2. Model:
   - XGBoost Classifier
   - Maqsad: signal ishlaydimi (1) yoki yo‘qmi (0) ni bashorat qilish
   - Chiqish: 0 dan 1 gacha confidence score
   - Faqat confidence > 75% bo‘lgan signallarni ko‘rsat

3. Trening ma'lumotlari:
   - Oxirgi 6-12 oylik tarixiy ma'lumotlar
   - Har bir signal uchun natija (profit/loss) yozib boriladi

--- TELEGRAM BOT FUNKSIYALARI ---

1. /start — botni ishga tushirish va qisqacha ko‘rsatma
2. Signal topilganda avtomatik xabar:
   🔔 YANGI POTENSIAL SIGNAL
   Juftlik: BTC/USDT
   Yo‘nalish: SHORT
   Ishonch: 84%
   Kuzatuv zonasi: 68,200 – 68,450
   Vaqt: NY Killzone (10:15 AM)
   Iltimos, hozirgi narxni yozib yuboring.

3. Men narxni yozib yuborganimda (masalan: "68340"):
   📊 TAHLL NATIJASI
   Entry: 68,340
   Stop-Loss: 68,580 (-0.35%)
   Take-Profit 1: 67,900 (+0.65%, R:R=1:1.85)
   Take-Profit 2: 67,450 (+1.3%, R:R=1:3.7)
   
   📝 Tahlil:
   - HTF (H4) da bearish divergensiya
   - Power of 3: Manipulation bosqichida yuqori likvidlik (Sweep High) olindi
   - Hozirgi narx Unicorn zonasiga (Breaker Block + FVG) qaytgan
   - ML modeli: 84% ishonch

4. /chart — so‘nggi tahlilni qayta ko‘rsatish
5. /status — hozirgi bozor holati (trend, sessiya, faol signallar)

--- TEXNIK TALABLAR ---

1. Kutubxonalar:
   - python-binance yoki ccxt (ma'lumotlar uchun)
   - pandas, numpy (ma'lumotlarni qayta ishlash)
   - xgboost (ML model)
   - python-telegram-bot (Telegram bot)
   - python-dotenv (kalitlarni saqlash)
   - schedule yoki APScheduler (skanerlash uchun)

2. Ma'lumotlar bazasi:
   - SQLite yoki PostgreSQL
   - Signallar, natijalar, model trening ma'lumotlarini saqlash

3. Xavfsizlik:
   - API kalitlar .env faylda saqlansin
   - Hech qanday buyurtma beruvchi API funksiyasi bo‘lmasin

--- KOD TUZILMASI ---

loyiha/
├── .env                     # API kalitlar, tokenlar
├── requirements.txt         # Kutubxonalar ro‘yxati
├── main.py                  # Asosiy ishga tushirish fayli
├── config.py                # Sozlamalar (vaqtlar, juftliklar)
├── data/
│   ├── market_data.py       # Binance/Bybit dan ma'lumot olish
│   └── database.py          # SQLite bilan ishlash
├── indicators/
│   ├── fvg.py               # Fair Value Gap deteksiyoni
│   ├── orderblock.py        # Order Block / Breaker Block
│   ├── liquidity.py         # Liquidity sweep deteksiyoni
│   ├── mss.py               # Market Structure Shift
│   ├── fibonacci.py         # OTE (0.618, 0.705, 0.786)
│   ├── amd.py               # Power of 3 (AMD)
│   └── unicorn.py           # Unicorn model (Breaker + FVG)
├── ml/
│   ├── features.py          # Feature engineering
│   ├── train.py             # XGBoost trening
│   └── predict.py           # Signal prediction
├── strategy/
│   ├── combo.py             # Barcha modellarni birlashtirish
│   └── risk.py              # SL/TP hisoblash
├── bot/
│   ├── telegram_bot.py      # Telegram bot handler
│   └── messages.py          # Xabar formatlari
└── scheduler/
    └── scanner.py           # Vaqtli skanerlash

--- MEN KUTAYOTGAN NATIJA ---

1. To‘liq ishlaydigan Python kodi (yuqoridagi tuzilmada)
2. Har bir fayl uchun qisqacha tushuntirish
3. O‘rnatish va ishga tushirish bo‘yicha qo‘llanma (README)
4. XGBoost modelini o‘z ma'lumotlarim bilan qanday train qilishim haqida ko‘rsatma
5. Telegram botni qanday sozlash va ishga tushirish

ILTIMOS: Kodni yozishda har bir qadamni aniq va tushunarli qilib, 
izohlar (comments) bilan boyitib yoz. Men Python bo‘yicha o‘rta darajada 
bilimga egaman.
