# ICT‑ML Telegram Signal System

A Python‑based trading‑signal framework that combines **Inner Circle Trader (ICT)**
methodology with a lightweight **XGBoost** machine‑learning filter and delivers
results through a **Telegram bot**.

---

## 📂 Project Structure
```
model/loyiha/
├─ .env                 # API keys & secrets (copy from example)
├─ requirements.txt     # Python dependencies
├─ main.py               # Entry point – starts scheduler & bot
├─ config.py             # Central configuration
├─ data/
│   ├─ market_data.py   # Binance/Bybit OHLCV fetcher
│   └─ database.py       # SQLAlchemy models (signals, results)
├─ indicators/
│   ├─ fvg.py           # Fair‑Value‑Gap detection
│   ├─ liquidity.py     # Liquidity‑Sweep detection
│   ├─ mss.py           # Market‑Structure‑Shift detection
│   ├─ fibonacci.py     # OTE zone calculation
│   ├─ amd.py           # Power‑of‑3 (Manipulation) helper
│   └─ unicorn.py       # Breaker‑Block + FVG overlap
├─ ml/
│   ├─ features.py      # Feature engineering
│   ├─ train.py          # XGBoost training script
│   └─ predict.py        # Model inference wrapper
├─ strategy/
│   ├─ combo.py         # Combines indicators + ML confidence
│   └─ risk.py          # SL/TP calculation (RRR 1:1.85 & 1:3.7)
├─ bot/
│   ├─ telegram_bot.py  # Bot handlers & polling loop
│   └─ messages.py       # Message templates
└─ scheduler/
    └─ scanner.py       # APScheduler job that triggers a signal
```

---

## 🚀 Getting Started
### 1️⃣ Prerequisites
* Python **3.10+**
* Git (to clone the repo)
* Access to Binance **or** Bybit API keys (read‑only)
* A Telegram Bot token (create via `@BotFather`)

### 2️⃣ Clone & Install
```bash
# Clone the repository (replace with your own URL if needed)
git clone https://github.com/yourname/ict-ml-telegram.git
cd model/loyiha

# Create a virtual environment
python -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3️⃣ Configure environment variables
Copy the example `.env` file, fill in your real credentials, then **do not** commit it.
```bash
cp .env .env.local   # or simply edit .env directly
```
```
# .env (example)
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
# or Bybit variables
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789   # Your personal chat ID or group ID
```

### 4️⃣ Initialise the database
```bash
python -c "from data.database import init_db; init_db()"
```
A SQLite file `signals.db` will be created in the project root.

### 5️⃣ (Optional) Train the XGBoost model
If you have historic labelled signals, populate the ``signals`` table with a
``confidence`` column and run:
```bash
python ml/train.py
```
The model will be saved as `ml_model.json`. The scaffolding already contains a
minimal trainer that treats confidence ≥ 0.8 as a positive example.

### 6️⃣ Run the system
```bash
python main.py
```
* The **APScheduler** will call the market scanner every
  `SCAN_INTERVAL_MINUTES` (default 5 min).
* When a signal with confidence > 75 % is generated, the bot sends a message to
  the chat defined by ``TELEGRAM_CHAT_ID``.
* Reply to the bot with the current price (e.g. `68340`). The bot will reply
  with entry, stop‑loss, two take‑profits and a short analysis.

---

## 🛠️ Extending the Project
* **Add more ICT models** – create new modules under `indicators/` and expose
  them in `strategy/combo.py`.
* **Improve feature engineering** – enrich `ml/features.py` with additional
  technical indicators (RSI, ATR, etc.).
* **Swap the database** – change `DATABASE_URL` in `.env` to a PostgreSQL URL and
  run migrations accordingly.
* **Deploy** – run the script on a VPS or cloud service; consider using a
  process manager (`systemd`, `pm2`, Docker) for reliability.

---

## 📜 License & Credits
* This scaffold is released under the MIT License.
* ICT methodology reference – Inner Circle Trader community.
* ML component – XGBoost (Apache‑2.0).

---

**Happy trading!** If you encounter any issues, feel free to open an issue on the
repository or adjust the configuration as needed.
