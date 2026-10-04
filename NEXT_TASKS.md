# Keyingi Ishlar Ro'yxati (NEXT TASKS)

Holat sanasi: 2026-10-03
Tekshirilgan: `main` branch, 7 commit, 68 tracked fayl, testlar: **45 passed** (`python3 -m pytest tests/`).

Quyidagi ro'yxat kodni o'qib chiqish (code review) natijasida topilgan aniq muammolar va
rivojlantirish yo'nalishlari asosida tuzilgan. Har bir band ustuvorlik bo'yicha tartiblangan.

---

> ✅ **P0 (1–4) va P1 (5–9) tuzatildi.** Pastdagi tavsiflar muammoni hujjatlashtiradi.
> Qolgan ishlar: P2 (kod sifati/infra) va P3 (yangi funksiyalar).

## 🔴 P0 — Kritik xatolar (1–4 tuzatildi ✅)

### 1. Paper trading boshlang'ich balansi noto'g'ri (50000 → 10000)
**Fayl:** [engine/paper_trading.py:18](loyiha/engine/paper_trading.py#L18)
```python
initial_balance = getattr(config_module, "INITIAL_BALANCE", 10000.0) if "config_module" in globals() else 10000.0
```
`config_module` hech qachon import qilinmagan, shuning uchun shart doim `False` bo'lib,
`10000.0` qiymatiga tushib qoladi. Natijada Prop Firm uchun mo'ljallangan **$50,000** o'rniga
**$10,000** bilan hisoblanadi va barcha risk/sizing natijalari buziladi.
**Tuzatish:** `from config import INITIAL_BALANCE` qilib to'g'ridan-to'g'ri ishlatish.

### 2. Bir signal uchun Telegramga 2 marta xabar ketadi (dublikat alert)
**Fayllar:** [bot/telegram_bot.py:124](loyiha/bot/telegram_bot.py#L124) va [services/notification_service.py:55](loyiha/services/notification_service.py#L55)
`SIGNAL_GENERATED` hodisasiga ikki mustaqil subscriber `format_signal_alert()` natijasini
bir xil `TELEGRAM_CHAT_ID` ga yuboradi. Deduplikatsiya (idempotency) ikkalasida ham alohida,
shuning uchun bir signal → ikki xabar.
**Tuzatish:** bitta yuborish yo'lini qoldirish (masalan, faqat `NotificationService`),
`handle_new_signal` ni esa faqat holat (state) yangilash uchun ishlatish.

### 3. `requirements.txt` to'liq emas — o'rnatish muvaffaqiyatsiz bo'ladi
**Fayl:** [requirements.txt](loyiha/requirements.txt)
Kodda import qilinadigan, lekin ro'yxatda yo'q paketlar:
`yfinance` (asosiy ma'lumot manbai — NQ/ES/GC shundan olinadi), `easyocr` (chart OCR),
`joblib` (model load), `matplotlib` (chart generator), `pybit` (Bybit live).
**Tuzatish:** barchasini versiyalari bilan qo'shish.

### 4. Ikkita raqobatlashuvchi "live execution" moduli mavjud
**Fayllar:** [engine/live_executor.py](loyiha/engine/live_executor.py) va [services/order_execution_service.py](loyiha/services/order_execution_service.py)
- `live_executor.py` — `qty=0.001` qattiq kodlangan, SL/TP yo'q, **aynan shu** `telegram_bot` ga ulangan.
- `order_execution_service.py` — to'g'ri SL/TP va position sizing bilan, lekin hech qayerda chaqirilmaydi.
- Bu `rule.md` dagi **"hech qanday buyurtma beruvchi API funksiyasi bo'lmasin"** talabiga ham zid.
**Tuzatish:** bittasini tanlash. Tavsiya: avtomatik savdoni butunlay olib tashlab, faqat signal
tizimi sifatida qoldirish yoki `LIVE_TRADING_ENABLED` ni majburiy `False` qilib qulflash.

---

## 🟠 P1 — Ishonchlilik va xavfsizlik (5–9 tuzatildi ✅)

### 5. Bozor yopiq paytda skanerlash
**Fayllar:** [services/exchange_service.py](loyiha/services/exchange_service.py) (`is_market_open()`) → [scheduler/scanner.py](loyiha/scheduler/scanner.py)
`is_market_open()` funksiyasi mavjud, lekin skaner uni chaqirmaydi. Dam olish kunlari yfinance
eskirgan (stale) sham qaytaradi va soxta signallar hosil bo'ladi.
**Tuzatish:** `scan_market()` boshida bozor yopiqligini tekshirib, erta chiqish.

### 6. Dashboard'da qattiq kodlangan parol
**Fayl:** [dashboard/app.py:30](loyiha/dashboard/app.py#L30)
```python
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "antigravity2026")
```
Agar `.env` da o'rnatilmasa, standart parol bilan ochiq qoladi. Dashboard `0.0.0.0:5000` da ishlaydi.
**Tuzatish:** default parolni olib tashlash, `.env` bo'sh bo'lsa ishga tushmaslik.

### 7. `/api/config` POST soxta — hech narsani saqlamaydi
**Fayl:** [dashboard/app.py:80](loyiha/dashboard/app.py#L80)
`{"status": "success"}` qaytaradi, ammo `config_local.json` ga yozmaydi. Sozlamalar UI dan
o'zgartirilmaydi.
**Tuzatish:** `config_local.json` ga real yozish yoki endpointni olib tashlash.

### 8. Xatolik ogohlantirishlarida cooldown yo'q
**Fayl:** [services/error_monitor.py](loyiha/services/error_monitor.py)
`notify_admin_error` har xatoda Telegramga yuboradi; skaner siklida takrorlansa admin chat
spam bo'ladi. Shuningdek `asyncio.run()` chaqiruvi ishlab turgan loop bilan to'qnashishi mumkin.
**Tuzatish:** bir xil xato uchun rate-limit/cooldown (masalan, 5 daqiqa) qo'shish.

### 9. Deduplikatsiya faqat xotirada — restartda yo'qoladi
**Fayl:** [scheduler/scanner.py:14](loyiha/scheduler/scanner.py#L14)
`last_alerted_candle` dict jarayon qayta ishga tushganda tozalanadi → bir xil sham uchun
qayta alert ketishi mumkin.
**Tuzatish:** oxirgi yuborilgan candle timestamp'ni DB da saqlash.

---

## 🟡 P2 — Kod sifati va infratuzilma

### 10. Risk hisoblashda ikkita ziddiyatli formula
**Fayllar:** [engine/risk_manager.py](loyiha/engine/risk_manager.py) (qattiq 1% SL, RRR 1:2) va
[strategy/risk.py](loyiha/strategy/risk.py) (ATR-based, RRR 1:1.85 va 1:3.70)
Paper trading va Telegram tahlili turli SL/TP beradi.
**Tuzatish:** yagona `strategy/risk.py` ni ikkalasida ham ishlatish.

### 11. `config.py` dagi `SILVER_BULLET_TIMES` ishlatilmaydi va zid
**Fayl:** [config.py:45](loyiha/config.py#L45) vs [indicators/silver_bullet.py:20](loyiha/indicators/silver_bullet.py#L20)
Config: `07:00–08:00, 14:00–15:00, 18:00–19:00`; indikatorda qattiq kodlangan: `08:00–09:00,
15:00–16:00, 19:00–20:00`. Config'dagi qiymat umuman o'qilmaydi.
**Tuzatish:** killzone oynalarini config orqali boshqariladigan qilish.

### 12. `dashboard/templates/index.html` ishlatilmaydi
**Fayl:** [dashboard/app.py:47](loyiha/dashboard/app.py#L47)
`render_template_string` bilan inline HTML ishlatiladi, mavjud template esa e'tiborsiz qolgan.
**Tuzatish:** `render_template("index.html")` ga o'tish.

### 13. Git repoda tozalash ishlari
- `loyiha/ml_model.json` (780 KB binary) git'da tracked — model faylini git'dan chiqarish yoki release asset sifatida saqlash.
- `loyiha/scratch_test_ocr_parser.py` — scratch fayl repoda qolgan.
- `.env.example` yo'q, lekin `.env` izohida "copy from .env.example" deb yozilgan.
- `loyiha/README.md` va root `README.md` ikkalasi mavjud — biri eskirgan bo'lishi mumkin.

### 14. CI / avtomatlashtirilgan test yo'q
`.github/workflows` yo'q, Dockerfile yo'q. 45 ta test mavjud, lekin har commit'da avtomatik ishlamaydi.
**Tuzatish:** GitHub Actions (pytest + lint) va Dockerfile qo'shish.

### 15. Test qamrovi bo'shliqlari
Mavjud 45 test quyidagilarni qamramaydi: `paper_trading` balans hisobi, `live_executor`,
scanner deduplikatsiya, dashboard auth, `notify_admin_error` rate-limit.

---

## 🟢 P3 — Rivojlantirish g'oyalari (yangi funksiyalar)

16. **Backtest CLI** — `BacktestEngine` mavjud, lekin uni ishga tushirish uchun alohida skript
    yo'q (`/backtest` faqat qo'llanma matni qaytaradi). Tarixiy CSV bilan to'liq hisobot chiqarish.
17. **Walk-forward hisobot** — `ml/walk_forward.py` natijalarini Telegramga chiqarish.
18. **Signal natijasini kuzatish** — signal berilgandan keyin TP/SL ga yetganini avtomatik
    tekshirib, winrate statistikasini DB da yuritish (hozir `Result` jadvali bo'sh qolmoqda).
19. **Ko'p foydalanuvchi (multi-user)** — hozir hamma sozlamalar bitta `TELEGRAM_CHAT_ID` ga bog'langan.
20. **Strukturaviy logging** — JSON loglar va log rotatsiyasi (hozir `logging.basicConfig`).

---

## Tavsiya etilgan tartib

| Bosqich | Bandlar | Natija |
|---------|---------|--------|
| ✅ 1-hafta | #1, #2, #3, #4 | Kritik buglar va o'rnatish muammosi tuzatildi |
| ✅ 2-hafta | #5, #6, #7, #8, #9 | Xavfsizlik va barqarorlik tuzatildi |
| ✅ 3-hafta | #10, #11, #12, #13, #14, #15 | Kod sifati, CI pipeline, 84 ta test to'liq muvaffaqiyatli |
| Keyin | #16–#20 | Yangi funksiyalar (Backtest CLI, walk-forward, multi-user) |

### Tuzatishlar yuzasidan xulosa

* **#7 (`/api/config` POST)** — **Tuzatildi**: `config_local.json` fayliga xavfsiz yoziladi va runtime konfiguratsiyani dinamik yangilaydi.
* **#10 (Risk unifikatsiyasi)** — **Tuzatildi**: `RiskManager` va `strategy.risk` ATR-based SL/TP bilan birlashtirildi.
* **#14 (CI workflow)** — **Tuzatildi**: `.github/workflows/ci.yml` Python 3.9–3.12 test matritsasi bilan yaratildi.
* **#15 (Test qamrovi)** — **Tuzatildi**: `test_p1_hardening.py` va `test_p2_quality.py` qo'shildi (jami 84 test).
* **Test holati:** **84 passed** (45 ➡️ 84).
