# 🚀 ICT-ML Trading Signal System

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Machine Learning](https://img.shields.io/badge/ML-XGBoost-orange.svg)](https://xgboost.readthedocs.io/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0.svg)](https://core.telegram.org/bots)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**ICT-ML Trading Signal System** — **Inner Circle Trader (ICT)** professional savdo metodologiyasi va **Machine Learning (XGBoost)** sun'iy intellekt filtri asosida real-vaqt rejimida kriptovalyuta bozorini (Binance/Bybit API) skanerlaydigan va **Telegram Bot** orqali yuqori aniqlikdagi savdo signallari hamda tahlillarni taqdim etuvchi avtomatlashtirilgan tizim.

> ⚠️ **MUHIM OGOHLANTIRISH**: Ushbu tizim **hech qachon avtomatik ravishda birjada savdo (buyurtma) ochmaydi**. Tizim faqat bozor tahlili va signallarini beruvchi professional savdo yordamchisidir (Trading Assistant). Savdo buyurtmalarini treyder o'zi qo'lda ochadi.

---

## 📌 Qilingan Ishlar va Loyiha Xususiyatlari

Ushbu loyiha doirasida quyidagi to'liq modullar va funksionalliklar nol loyihalangan, implementatsiya qilingan va sinovdan o'tkazilgan:

### 1. 📐 ICT Indikatorlari va Smart Money Modellari (`indicators/`)
Loyiha ICT metodologiyasining 6 ta asosiy modelini avtomatik aniqlash algoritmlarini o'z ichiga oladi:
* **ICT 2022 Mentorship Model** (`fvg.py`, `liquidity.py`, `mss.py`):
  * **Liquidity Sweep**: Oldingi Swing High/Low hamda Equal Highs/Lows nuqtalaridan likvidlik yutib olinishini aniqlash.
  * **Displacement**: Keskin impulsiv narx harakati.
  * **MSS (Market Structure Shift)**: Bozor strukturasi siljishi va trend o'zgarishi.
  * **FVG (Fair Value Gap)**: 3 shamlik nomutanosiblik zonalarini avtomatik aniqlash.
* **Silver Bullet Model** (`silver_bullet.py`):
  * Faqat belgilangan Killzone vaqt oraliqlarida (EST bo'yicha: London `03:00–04:00`, NY Morning `10:00–11:00`, NY Afternoon `14:00–15:00`) likvidlik sweep va FVG hosil bo'lishini skanerlash.
* **Power of 3 / AMD** (`amd.py`):
  * **Accumulation**: Osiyo sessiyasidagi tor diapazon.
  * **Manipulation**: London ochilishidagi soxta breakout (Likvidlik yutish).
  * **Distribution**: Nyu-York sessiyasidagi asosiy yo'nalishli harakat.
* **OTE (Optimal Trade Entry)** (`fibonacci.py`):
  * Fibonacci `0.618`, `0.705`, `0.786` darajalari va unga mos keluvchi FVG zonalarini hisoblash.
* **Unicorn Model** (`unicorn.py`, `orderblock.py`):
  * **Breaker Block** va **FVG** zonalarining bir xil diapazonda ustma-ust tushishini (overlap) aniqlash. Eng yuqori ehtimollikdagi signal.
* **HTF Bias & MMBM/MMSM** (`htf_bias.py`):
  * Yuqori taymfreym (HTF H4/D1) institutsional yo'nalishini aniqlash.

---

### 2. 🤖 Machine Learning (XGBoost) Filtr Moduli (`ml/`)
Signal sifatini oshirish va "yolg'on signallarni" elash uchun AI filtr integratsiya qilingan:
* **Feature Engineering (`features.py`)**:
  * FVG kattaligi, yoshi va narxga masofasi;
  * Order Block va Breaker Block kuchi;
  * Liquidity sweep borligi;
  * Savdo sessiyasi turi va kun soati;
  * RSI, ATR hamda hajm (Volume) ko'rsatkichlari;
  * OTE zonasiga to'g'ri kelish ko'rsatkichi (0.0-1.0).
* **XGBoost Classifier (`train.py`, `train_universal_model.py`, `train_on_csv.py`)**:
  * Signal uchun **Confidence Score** (0% dan 100% gacha) hisoblaydi.
  * Faqat ishonchlilik foizi **75% dan yuqori** bo'lgan signallar Telegramga yuboriladi.
* **Retraining va Tuning (`retrain.py`, `tune.py`, `dataset_builder.py`)**:
  * Tarixiy ma'lumotlar yoki SQLite da toplangan signallar bo'yicha modelni qayta o'rgatish imkoniyati.

---

### 3. 💬 Telegram Bot & Interfeys (`bot/`)
Tizim foydalanuvchi bilan Telegram orqali real-vaqt rejimida muloqot qiladi:
* **Avtomatik Bildirishnomalar**:
  * Signal topilganda juftlik, yo'nalish (LONG/SHORT), Confidence foizi, kuzatuv zonasi va sessiya haqida darhol xabar keladi.
* **Dinamik Narx Tahlili va Risk Management (`strategy/risk.py`)**:
  * Foydalanuvchi signalga javoban joriy narxni yuborishi bilan (masalan: `68340`), bot darhol:
    * Aniq **Entry** nuqtasi;
    * **Stop-Loss (SL)**;
    * **Take-Profit 1** (RRR `1:1.85`);
    * **Take-Profit 2** (RRR `1:3.7`);
    * Texnik va ICT omillariga asoslangan matnli tahlilni taqdim etadi.
* **Bot Buyruqlari**:
  * `/start` — Botni ishga tushirish va qo'llanma;
  * `/status` — Tizim holati, trend va faol skanerlash ma'lumotlari;
  * `/chart` — So'nggi tahlil grafiklarini qayta ko'rsatish.

---

### 4. 📊 Grafik Vizualizatsiyasi va Web Dashboard (`services/`, `dashboard/`)
* **Chart Generator (`chart_generator.py`)**: Matplotlib yordamida shamlar (candlesticks), indicator va FVG/Unicorn zonalarini grafik rasm shaklida chizib, Telegramga jo'natadi.
* **Chart OCR Parser (`chart_ocr.py`)**: Grafik rasmlaridan narx va darajalarni OCR yordamida o'qish qobiliyati.
* **Web Dashboard (`dashboard/app.py`)**: Flask freymvorkida yaratilgan interfeys bo'lib, signallar statistikasi va tizim metrikalarini brauzerda kuzatish imkonini beradi.

---

### 5. ⚙️ Event-Driven Arxitektura va Skaner (`events/`, `scheduler/`, `data/`)
* **APScheduler (`scanner.py`)**: Har 5 va 15 daqiqalik intervallarda Binance/Bybit birjalarini avtomatik skanerlaydi.
* **Event Bus (`event_bus.py`)**: Modullar o'rtasida asinxron xabarlar almashinuvi.
* **SQLAlchemy ORM (`database.py`, `data_warehouse.py`)**: Signallar, natijalar hamda tarixiy OHLCV ma'lumotlarini SQLite ma'lumotlar bazasida saqlash.

---

## 📂 Loyiha Strukturasi

```
loyiha/
├── main.py                    # Asosiy ishga tushirish nuqtasi (Scheduler + Telegram Bot)
├── config.py                  # Markaziy sozlamalar (API kalitlar, juftliklar, vaqtlar)
├── requirements.txt           # Python bog'liqliklari (dependencies)
├── run.sh                     # Tizimni bir bosqichda ishga tushirish skripti
├── ml_model.json              # O'rgatilgan XGBoost model fayli
├── setup_telegram_menu.py     # Telegram bot menyusini sozlash skripti
│
├── bot/                       # Telegram Bot moduli
│   ├── telegram_bot.py        # Bot buyruqlari va hodisalarini boshqarish
│   └── messages.py            # Telegram xabar shablonlari
│
├── indicators/                # ICT Texnik ko'rsatkichlari
│   ├── fvg.py                 # Fair Value Gap deteksiyasi
│   ├── orderblock.py          # Order Block / Breaker Block
│   ├── liquidity.py           # Liquidity Sweep deteksiyasi
│   ├── mss.py                 # Market Structure Shift
│   ├── fibonacci.py           # OTE (0.618, 0.705, 0.786) hisoblash
│   ├── amd.py                 # Power of 3 (Accumulation, Manipulation, Distribution)
│   ├── silver_bullet.py       # Silver Bullet modeli
    ├── unicorn.py             # Unicorn modeli (Breaker Block + FVG)
│   └── htf_bias.py            # HTF Bias aniqlash
│
├── ml/                        # Machine Learning moduli
│   ├── features.py            # Feature engineering (alomatlar ajratish)
│   ├── train.py               # XGBoost modelini o'rgatish
│   ├── train_universal_model.py # Ko'p juftlikli universal model o'rgatish
│   ├── train_on_csv.py        # CSV fayllardan model o'rgatish
│   ├── predict.py             # Model prediksiyasi va confidence hisobi
│   ├── retrain.py             # Modelni qayta o'rgatish
│   └── tune.py                # Hyperparameter tuning
│
├── strategy/                  # Savdo strategiyasi va Risk menejment
│   ├── combo.py               # Barcha ICT modellari va ML natijalarini birlashtirish
│   ├── risk.py                # Dynamic Entry, Stop-Loss va Take-Profit (1:1.85 & 1:3.7)
│   ├── base.py                # Asosiy strategiya bazaviy sinfi
│   └── engine.py              # Strategiya dvigateli
│
├── services/                  # Qo'shimcha servislar
│   ├── exchange_service.py    # Binance / Bybit ulanishi va uzoq muddatli barqarorlik
│   ├── chart_generator.py     # Narx va signallar grafigini rasmga chizish
│   ├── chart_ocr.py           # Grafik rasmlardan ma'lumotlarni o'qish (OCR)
│   ├── order_execution_service.py # Buyurtmalarni boshqarish servisi
│   ├── notification_service.py# Bildirishnomalar servisi
│   └── error_monitor.py       # Xatoliklar monitoringi
│
├── dashboard/                 # Web Monitoring Dashboard
│   ├── app.py                 # Flask web server
│   └── templates/             # Dashboard HTML shablonlari
│
├── data/                      # Ma'lumotlar bazasi va tarixiy ma'lumotlar
│   ├── database.py            # SQLAlchemy modellar (signals, results)
│   ├── market_data.py         # Real-time OHLCV yuklagich
│   ├── fetch_historical.py    # Tarixiy sham ma'lumotlarini yuklash
│   └── data_warehouse.py      # Ma'lumotlar ombori
│
├── scheduler/                 # Bozor skaneri va Rejalashtiruvchi
│   └── scanner.py             # APScheduler orqali avtomatik skanerlash
│
├── events/                    # Event-driven arxitektura
│   └── event_bus.py           # Hodisalar marshrutizatori
│
└── tests/                     # Testlar toplami
```

---

## 🛠️ Texnologiyalar Steki (Tech Stack)

* **Dasturlash tili**: Python 3.10+
* **Machine Learning**: XGBoost, Scikit-learn, Pandas, NumPy
* **Interfeys**: `python-telegram-bot` (v20+)
* **Bozor Ma'lumotlari**: `python-binance`, `ccxt`, `requests`
* **Ma'lumotlar Bazasi**: SQLite, SQLAlchemy ORM
* **Vaqt Rejalashtiruvchi**: APScheduler
* **Web Dashboard**: Flask
* **Grafik va Vizualizatsiya**: Matplotlib, PIL (Pillow)

---

## 🚀 O'rnatis va Ishga Tushirish Qo'llanmasi

### 1️⃣ Talablar (Prerequisites)
* Python **3.10** yoki undan yuqori versiya;
* Git;
* Telegram Bot Token ([@BotFather](https://t.me/BotFather) orqali olinadi);
* Binance yoki Bybit API kalitlari (read-only rejimi yetarli).

---

### 2️⃣ Repozitoriyani klonlash va o'rnatish
```bash
# Repozitoriyani yuklab oling
git clone https://github.com/your-username/algo-trading.git
cd algo-trading/loyiha

# Virtual muhit yaratish
python3 -m venv venv

# Virtual muhitni aktivlashtirish
# MacOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# Kerakli kutubxonalarni o'rnatish
pip install -r requirements.txt
```

---

### 3️⃣ `.env` Konfiguratsiya Faylini Sozlash
`loyiha` papkasi ichida `.env` faylini yarating va quyidagi o'zgaruvchilarni kiriting:

```env
# Binance API sozlamalari
BINANCE_API_KEY=sizning_binance_api_keyingiz
BINANCE_API_SECRET=sizning_binance_api_secretingiz

# Telegram Bot sozlamalari
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyZ
TELEGRAM_CHAT_ID=123456789 # Shaxsiy Telegram ID yoki Guruh ID

# Bozor va Skaner sozlamalari
SCAN_INTERVAL_MINUTES=5
DATABASE_URL=sqlite:///signals.db
```

---

### 4️⃣ Ma'lumotlar Bazasini Initsializatsiya Qilish
SQLite `signals.db` bazasini yaratish uchun quyidagi buyruqni bering:

```bash
python -c "from data.database import init_db; init_db()"
```

---

### 5️⃣ Tizimni Ishga Tushirish

Tizimni quyidagi buyruq orqali ishga tushirishingiz mumkin:

```bash
python main.py
```
yoki qulay `run.sh` skriptidan foydalaning:
```bash
chmod +x run.sh
./run.sh
```

**Ish jarayoni:**
1. **APScheduler** har 5 daqiqada belgilangan kripto juftliklarni (masalan: `BTC/USDT`, `ETH/USDT`) skanerlaydi.
2. Signal topilganda **XGBoost ML** modeli signal sifatini baholaydi.
3. Confidence score > 75% bo'lsa, Telegram bot chatga bildirishnoma yuboradi.

---

### 6️⃣ (Ixtiyoriy) Web Dashboardni Ishga Tushirish
Signallar va metrikalarni veb-interfeys orqali kuzatish uchun:

```bash
python dashboard/app.py
```
Brauzerda `http://127.0.0.1:5000` manziliga kiring.

---

## 📱 Telegram Botdan Foydalanish

### 1. Signal Kelganda Avtomatik Xabar:
```text
🔔 YANGI POTENSIAL SIGNAL

Juftlik: BTC/USDT
Yo‘nalish: SHORT
Ishonch (ML Score): 84%
Kuzatuv zonasi: 68,200 – 68,450
Vaqt: NY Killzone (10:15 AM)
Model: Unicorn (Breaker Block + FVG)

Iltimos, hozirgi narxni yozib yuboring (masalan: 68340).
```

### 2. Narx Yuborilganda Qaytariladigan Tahlil Natijasi:
```text
📊 TAHLIL NATIJASI

Entry: 68,340
Stop-Loss: 68,580 (-0.35%)
Take-Profit 1: 67,900 (+0.65%, R:R = 1:1.85)
Take-Profit 2: 67,450 (+1.30%, R:R = 1:3.70)

📝 Texnik Tahlil:
• HTF (H4) da Bearish struktura saqlanib qolgan
• Power of 3: Manipulation bosqichida yuqori likvidlik (Sweep High) olindi
• Narx Unicorn zonasiga (Breaker Block + FVG) qaytgan
• XGBoost ML Modeli: 84% ishonch darajasi
```

---

## 🧠 Machine Learning Modelni Qayta O'rgatish (Training)

Agar siz o'zingizning tarixiy sham ma'lumotlaringiz bo'yicha XGBoost modelini qayta o'rgatmoqchi bo'lsangiz:

1. Tarixiy ma'lumotlarni yuklab oling:
   ```bash
   python data/fetch_historical.py
   ```
2. DataSet va Feature larni shakllantiring:
   ```bash
   python ml/dataset_builder.py
   ```
3. Universal ML modelini o'rgating:
   ```bash
   python ml/train_universal_model.py
   ```
Yangi o'rgatilgan model `ml_model.json` ko'rinishida saqlanadi va tizim tomonidan avtomatik qo'llaniladi.

---

## 📜 Litsenziya

Ushbu loyiha **MIT License** asosida litsenziyalangan.

---

## 👨‍💻 Yaratuvchi va Rahmatlar

* **ICT Metodologiyasi**: Michael J. Huddleston (Inner Circle Trader) ta'limotlari asosida shakllantirilgan.
* **ML Texnologiyasi**: XGBoost Open Source Community.

---
**Omadli va intizomli savdo tilaymiz! 📈**
