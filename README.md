# Algo Trading (ICT + ML + Telegram)

Ushbu repository `loyiha/` papkasida joylashgan **ICT metodologiyasiga asoslangan savdo signal tizimi**ni o‘z ichiga oladi. Tizim bozorni periodik skanerlaydi, signalga ML confidence beradi va Telegram bot orqali tahlil yuboradi.

## Asosiy imkoniyatlar

- ICT indikatorlari: FVG, Liquidity Sweep, MSS, OTE, Unicorn, AMD, Silver Bullet
- Multi-asset monitoring: `NQ`, `ES`, `GC` (hamda ayrim crypto juftliklar)
- XGBoost asosidagi confidence filtri
- Telegram bot buyruqlari: `/start`, `/status`, `/chart`, `/backtest`, `/risk`, `/settings`, `/help`
- SQLite/PostgreSQL orqali signal va natijalarni saqlash
- Flask dashboard (`dashboard/app.py`) orqali API va monitoring
- Haftalik avtomatik model retraining scheduler

## Repository tuzilmasi

```text
algo-trading/
├── README.md
├── rule.md
└── loyiha/
    ├── main.py
    ├── config.py
    ├── requirements.txt
    ├── bot/
    ├── data/
    ├── indicators/
    ├── ml/
    ├── scheduler/
    ├── services/
    ├── strategy/
    ├── dashboard/
    └── tests/
```

## Tez ishga tushirish

### 1) Muhit tayyorlash

```bash
cd /home/runner/work/algo-trading/algo-trading/loyiha
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) `.env` sozlash

`loyiha/.env` fayl yarating va kamida quyidagilarni kiriting:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

BINANCE_API_KEY=
BINANCE_API_SECRET=
BYBIT_API_KEY=
BYBIT_API_SECRET=

DATABASE_URL=sqlite:///./signals.db
LIVE_TRADING_ENABLED=false

USE_WEBHOOK=false
WEBHOOK_URL=
WEBHOOK_PORT=8443
WEBHOOK_LISTEN=0.0.0.0
```

> `LIVE_TRADING_ENABLED=false` default holatda real order yuborilmaydi.

### 3) Loyihani ishga tushirish

```bash
python main.py
```

Yoki:

```bash
bash run.sh
```

## Dashboard

```bash
python dashboard/app.py
```

So‘ng brauzerda: `http://localhost:5000`

## Testlar

```bash
python -m unittest discover -s tests
```

## ML trening

Asosiy skriptlar:

- `ml/train.py` — bazaviy model treningi
- `ml/train_universal_model.py` — universal model treningi
- `ml/retrain.py` — qayta o‘qitish
- `ml/train_on_csv.py` — CSV dataset orqali trening/backtest

Misol:

```bash
python ml/train_universal_model.py
```

## Muhim eslatma

- API kalitlar va tokenlarni faqat `.env` ichida saqlang.
- `.env`, DB va model fayllarini ommaviy joyga chiqarishda ehtiyot bo‘ling.
- Real savdoni yoqishdan oldin risk parametrlari va order execution kodini tekshirib chiqing.
