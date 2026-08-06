# 🎯 ICT-ML Trading System — Texnik Suhbat (Interview Prep) Qo'llanmasi

Ushbu hujjat loyihangiz arxitekturasi, ICT va Machine Learning bilimlaringiz hamda dasturlash yondashuvingiz bo'yicha texnik suhbatga (Technical Interview) puxta tayyorgarlik ko'rishingiz uchun savol-javob ko'rinishida tuzilgan.

---

## 📑 MUNDARIJA

1. [📐 1. Loyiha Umumiy Ko'rinishi va Yondashuv (Architecture & Decisions)](#1-loyiha-umumiy-korinishi-va-yondashuv)
2. [📈 2. ICT Trading Metodologiyasi va Algoritmlar (Trading Strategy & Logic)](#2-ict-trading-metodologiyasi-va-algoritmlar)
3. [🤖 3. Machine Learning Pipeline va Feature Engineering (ML Engineering)](#3-machine-learning-pipeline-va-feature-engineering)
4. [💻 4. System Design, Dasturiy Arxitektura va Kod Sifati (Software Engineering)](#4-system-design-dasturiy-arxitektura-va-kod-sifati)
5. [🔥 5. Chuqur Texnik va Vasiylik Savollari (Deep Technical & Edge Cases)](#5-chuqur-texnik-va-vasiylik-savollari)

---

<a name="1-loyiha-umumiy-korinishi-va-yondashuv"></a>
## 📐 1. Loyiha Umumiy Ko'rinishi va Yondashuv

### ❓ S1: Loyihangizning asosiy maqsadi nima va nima uchun aynan ICT + Machine Learning gibrid yondashuvini tanlagansiz?
**💬 Javob:**
Loyihaning asosiy maqsadi — kriptovalyuta bozorida **Inner Circle Trader (ICT)** institutsional savdo metodologiyasi va **XGBoost Machine Learning** modelini birlashtirgan holda yuqori aniqlikdagi real-vaqt savdo signallarini aniqlash va Telegram orqali analitik taqdim etishdir.

**Gibrid yondashuv sababi:**
- **ICT indikatorlari** bozor kontekstini va institutsional izlarni (Fair Value Gap, Liquidity Sweep, Order Block) juda yaxshi tushunadi. Birodar indikatorlar kutilayotgan potensial zonani beradi, ammo ba'zan soxta (false positive) signallar ishlab chiqaradi.
- **Machine Learning (XGBoost)** esa faqat statik qoidalarga tayanmaydi. U ko'p o'lchamli indikatorlar (RSI, ATR, FVG yoshi, hajm, sessiya turi, OTE darajalari) o'rtasidagi munosabatlarni tahlil qilib, signalning g'alaba qozonish ehtimolini (Confidence Score) hisoblaydi va soxta signallarni elaydi.

---

### ❓ S2: Nima uchun tizim birjada avtomatik buyurtma (auto-execution) ochmaydi?
**💬 Javob:**
Bu **Risk-Management va Non-Custodial Security** tamoyillariga asoslangan ongli arxitekturaviy qaror:
1. **Risk Nazorati**: Bozor kutilmagan yangiliklar yoki kutilmagan spayklar paytida avtomatik robotlar katta yo'qotishlarga olib kelishi mumkin. Inson omili (Human-in-the-loop) so'nggi qarorni qabul qiladi.
2. **API Xavfsizligi**: Birja API kalitlariga faqat Read-Only (faktik narxlarni o'qish) huquqi beriladi. Bu mablag'larni o'g'irlash yoki ruxsat etilmagan buyurtmalar ochish xavfini nolga tushiradi.
3. **Erkinlik va Analitika**: Bot treyderga aniq Entry, Stop-Loss, Take-Profit 1 & 2 hamda texnik tahlilni taqdim etadi. Treyder buyurtmani o'z xohishi bo'yicha brokerda ochadi.

---

### ❓ S3: Ushbu loyihadagi Ma'lumotlar Oqimi (Data Flow) qanday tashkil etilgan?
**💬 Javob:**
1. **Data Ingestion**: `scheduler/scanner.py` (APScheduler) har 5/15 daqiqada `data/market_data.py` orqali Binance/Bybit REST/CCXT API dan real-vaqt OHLCV shamlarini tortadi.
2. **Pattern Recognition**: Shamlar `strategy/combo.py` va `indicators/` modullariga beriladi. ICT qoidalari bo'yicha shablonlar (FVG, Sweep, MSS, Unicorn) aniqlanadi.
3. **ML Inference**: Signal topilsa, `ml/features.py` orqali alomatlar vektori yig'iladi va `ml/predict.py` tayyor `ml_model.json` modeli orqali ishonchlilik foizini (Confidence Score) hisoblaydi.
4. **Filtering & Notification**: Agar Confidence > 75% bo'lsa, `bot/telegram_bot.py` orqali foydalanuvchiga bildirishnoma va vizual grafik jo'natiladi.
5. **Interactive Analysis**: Foydalanuvchi joriy narxni kiritgach, `strategy/risk.py` dinamik ravishda RRR 1:1.85 va 1:3.7 nisbatdagi SL/TP darajalarini qaytaradi.

---

<a name="2-ict-trading-metodologiyasi-va-algoritmlar"></a>
## 📈 2. ICT Trading Metodologiyasi va Algoritmlar

### ❓ S4: FVG (Fair Value Gap) va Liquidity Sweep larni kodingizda algoritmik ravishda qanday aniqlagansiz?
**💬 Javob:**
- **Fair Value Gap (`indicators/fvg.py`)**:
  - 3 ta ketma-ket sham ko'rib chiqiladi ($C_1, C_2, C_3$).
  - **Bullish FVG**: $C_1.\text{high} < C_3.\text{low}$. Gap oraliq: $[C_1.\text{high}, C_3.\text{low}]$.
  - **Bearish FVG**: $C_1.\text{low} > C_3.\text{high}$. Gap oraliq: $[C_3.\text{high}, C_1.\text{low}]$.
  - Boshqa shamlar ushbu zonaga qaytib, uni "mitigate" qilgan-qilmagani (`subsequent['low'].min() <= gap_low`) tekshiriladi. Shuningdek, bozor shovqinini elash uchun `min_gap_pct` (masalan 0.05%) sharti qo'yilgan.

- **Liquidity Sweep (`indicators/liquidity.py`)**:
  - Oxirgi swing yuqori/paski nuqtalar (Swing Highs/Lows) yoki teng tepaliklar (Equal Highs/Lows) aniqlanadi.
  - Joriy sham soyasi (wick) o'sha darajadan o'tib ketgan, lekin sham yopilishi (close) daraja ichida qolgan holat (Sweep) deb hisoblanadi.

---

### ❓ S5: Unicorn Model nima va uni dasturiy kodda aniqlash mantiqi qanday?
**💬 Javob:**
**Unicorn Model** — bu ICT metodologiyasidagi eng yuqori ehtimollikdagi (High Probability) setup bo'lib, **Breaker Block** va **FVG (Fair Value Gap)** bir xil narx diapazonida ustma-ust tushganida (overlap) hosil bo'ladi.

**Koddagi mantiq (`indicators/unicorn.py` va `indicators/orderblock.py`)**:
1. `orderblock.py` orqali strukturani yorib o'tgan Order Block (Breaker Block) diapazoni $[OB_{\text{low}}, OB_{\text{high}}]$ topiladi.
2. `fvg.py` orqali FVG diapazoni $[FVG_{\text{low}}, FVG_{\text{high}}]$ topiladi.
3. Overlap tekshiriladi:
   $$\text{Overlap} = \max(0, \min(OB_{\text{high}}, FVG_{\text{high}}) - \max(OB_{\text{low}}, FVG_{\text{low}}))$$
4. Agar Overlap > 0 va har ikki struktura yo'nalishi bir xil bo'lsa, Unicorn Model tasdiqlanadi.

---

### ❓ S6: Power of 3 (AMD) va Silver Bullet Killzone vaqtlarini qanday modellashtirgansiz?
**💬 Javob:**
- **Power of 3 / AMD (`indicators/amd.py`)**:
  - **Accumulation**: Osiyo sessiyasidagi (00:00 - 06:00 UTC) min/max narx diapazoni olinadi.
  - **Manipulation**: London ochilishida Osiyo diapazonidan tashqariga soxta breakout va likvidlik yutish (Sweep) tekshiriladi.
  - **Distribution**: NY sessiyasida asosiy trend yo'nalishidagi harakat kuzatiladi.

- **Silver Bullet Killzone (`indicators/silver_bullet.py`)**:
  - Nyu-York (EST) vaqti bo'yicha 3 ta qat'iy 1 soatlik interval belgilangan:
    - London: `03:00 - 04:00 EST`
    - NY Morning: `10:00 - 11:00 EST`
    - NY Afternoon: `14:00 - 15:00 EST`
  - Faqat ushbu soatlarda hosil bo'lgan FVG + Liquidity Sweep signallari Silver Bullet sifatida tasdiqlanadi.

---

### ❓ S7: Risk-Menejment va Stop-Loss/Take-Profit darajalari qanday hisoblanadi?
**💬 Javob:**
`strategy/risk.py` faylida:
- **Stop-Loss (SL)**: FVG yoki Order Block ning qarama-qarshi chegarasiga kichik filter (ATR yoki 0.1-0.2%) qo'shib belgilanadi.
- **Risk Amount**: $R = |\text{Entry} - \text{SL}|$.
- **Take-Profit 1 (TP1)**: Risk-to-Reward Ratio $1 : 1.85$ ($TP1 = \text{Entry} \pm 1.85 \times R$).
- **Take-Profit 2 (TP2)**: Risk-to-Reward Ratio $1 : 3.70$ ($TP2 = \text{Entry} \pm 3.70 \times R$).

---

<a name="3-machine-learning-pipeline-va-feature-engineering"></a>
## 🤖 3. Machine Learning Pipeline va Feature Engineering

### ❓ S8: XGBoost modeli uchun alomatlar (features) vectorida nimalar bor?
**💬 Javob:**
`ml/features.py` 30 ga yaqin o'ziga xos alomatlarni shakllantiradi:
1. **ICT Ko'rsatkichlari**: `fvg_detected`, `fvg_size`, `fvg_distance`, `liquidity_sweep`, `mss_detected`, `unicorn_detected`, `in_ote` (0.618-0.786 diapazonga tushish).
2. **Texnik Indikatorlar**: RSI (14), ATR (14), ATR nisbati (`total_range / atr_14`), Volume nisbati (`volume / volume_mean_10`), EMA9 va EMA21 farqi.
3. **Bozor Dinamikasi va Mikrostruktura**: Sham tanasi nisbati (`candle_body_ratio`), soya nisbatlari (`top_wick_ratio`, `bottom_wick_ratio`), Momentum (5 va 10 shamlik), Volatillik.
4. **Volume Profile va Session Proxy**: POC (Point of Control) masofasi, Kun soati (`hour_of_day`), Sessiya turi (Asian, London, NY).

---

### ❓ S9: Nima uchun Deep Learning (LSTM/Transformer) o'rniga XGBoost modelini tanladingiz?
**💬 Javob:**
1. **Tabular Data Samadorligi**: Moliyaviy va indikatorli jadvalli ma'lumotlarda (tabular data) Gradient Boosted Decision Trees (XGBoost/LightGBM) neyron tarmoqlaridan ko'ra barqaror va yuqori aniqlik beradi.
2. **Overfitting va Shovqin**: Moliya ma'lumotlari judayam shovqinli. Deep Learning modellari tezda overfitting bo'ladi. XGBoost da `max_depth` (masalan 4-6), `subsample=0.8`, `colsample_bytree=0.8` va `gamma` bilan regulyarizatsiya qilish osonroq.
3. **Inference Tezligi va Resurslar**: XGBoost mikrosekundlarda bashorat qiladi, CPU resurslarini kam sarflaydi va deployment qilish uchun atigi bitta yengil `ml_model.json` fayli yetarli.
4. **Interpretability (Tushunarlilik)**: Feature Importance (alomatlar muhimligi) orqali qaysi indikator model qaroriga ko'proq ta'sir qilayotganini tahlil qilish mumkin.

---

### ❓ S10: Bozor kelajagini o'tmishga sizdirish (Lookahead Bias / Data Leakage) muammosini qanday hal qildingiz?
**💬 Javob:**
Lookahead bias — algoritmlarda eng ko'p uchraydigan xato. Uni oldini olish uchun:
1. **Strict Indexing**: Har bir $t$ vaqtdagi alomatlarni hisoblashda faqat $t$ va undan oldingi yopilgan sham ma'lumotlari (`iloc[:-1]`) ishlatiladi. Joriy ochiq shamning yopilish narxi ishlatilmaydi.
2. **Target Labeling**: Model o'tmishdagi har bir signal bo'yicha $t+N$ shamlarda TP1 ga erishildimi yoki SL urildimi shuni aniqlab, target ($1$ yoki $0$) qo'yadi.

---

### ❓ S11: Data Drift (Bozor rejimi o'zgarishi) ga model qanday moslashadi?
**💬 Javob:**
`ml/retrain.py` va `data/fetch_historical.py` modullari orqali:
1. SQLite ma'lumotlar bazasida saqlanib borayotgan real signallar va uning fiksatsiya qilingan natijalari bo'yicha model belgilangan vaqt oraliqlarida (masalan har hafta) avtomatik qayta o'rgatiladi (Retraining).
2. Yangi bozor ma'lumotlari bilan giperparametrlarni qayta sozlash uchun `ml/tune.py` ishga tushiriladi.

---

<a name="4-system-design-dasturiy-arxitektura-va-kod-sifati"></a>
## 💻 4. System Design, Dasturiy Arxitektura va Kod Sifati

### ❓ S12: Telegram Bot va Skaner arxitekturasini tushuntiring. Ularning asinxron ishlashi qanday ta'minlangan?
**💬 Javob:**
- **Telegram Bot (`bot/telegram_bot.py`)**: `python-telegram-bot` v20+ freymvorkida **async/await** asynchronous event loop asosida ishlaydi. Bot foydalanuvchining narx kiritish xabarlarini to'siqsiz (non-blocking) qabul qiladi.
- **Scheduler (`scheduler/scanner.py`)**: **APScheduler** background process sifatida ishlaydi. U har 5 daqiqada asinxron ravishda bozor skanerlash vazifasini chaqiradi va Bot bilan Event Bus yoki direct async notification orqali aloqa qiladi.

---

### ❓ S13: Birja API (Binance/Bybit) bilan ishlashda tarmoq xatoliklari (Rate limits, Connection timeout) qanday boshqariladi?
**💬 Javob:**
`services/exchange_service.py` faylida:
1. **Exponential Backoff & Retries**: REST so'rov xatolik berganida (429 Rate limit yoki 5xx server error), tizim 1s, 2s, 4s kutib qayta urinadi.
2. **Failover Client**: Binance API ishlamay qolsa, CCXT / Bybit zaxira API clientiga avtomatik o'tish imkoniyati bor.
3. **Data Caching**: Har bir daqiqada bir xil OHLCV shamini qayta-qayta so'ramaslik uchun local kesh ishlatiladi.

---

### ❓ S14: Web Dashboard (`dashboard/app.py`) va Chart Generator (`chart_generator.py`) qanday vazifani bajaradi?
**💬 Javob:**
- **Chart Generator (`services/chart_generator.py`)**: `Matplotlib` kutubxonasi yordamida OHLCV shamlarini, FVG va Unicorn zonalarini rasm shaklida rendering qiladi va Telegram bot orqali foydalanuvchiga visual grafik ko'rinishida yuboradi.
- **Web Dashboard (`dashboard/app.py`)**: Flask freymvorkida yaratilgan yengil admin panel bo me'mori. U SQLite bazasiga ulanib, joriy faol signallar, g'alaba foizi (Win Rate), kunlik PnL va ML model samaradorligini brauzerda ko'rsatadi.

---

<a name="5-chuqur-texnik-va-vasiylik-savollari"></a>
## 🔥 5. Chuqur Texnik va Vasiylik Savollari

### ❓ S15: Ushbu loyihada siz duch kelgan eng murakkab texnik muammo nima bo'ldi va uni qanday hal qildingiz?
**💬 Javob (Namuna):**
"Eng murakkab muammo — **FVG Mitigation va Multi-Timeframe Alignment**ni to'g'ri algoritmlash bo'ldi. 
Dastlab FVG aniqlangandan so'ng kelajakdagi shamlar bu zonaga tegib o'tsa ham, uni qayta-qayta signal sifatida berish holati kuzatildi. 

**Yechim:** `fvg.py` faylida FVG ob'ektiga `mitigated` (boolean) va `age` (yosh) atributlarini kiritdik. FVG hosil bo'lgach, undan keyingi barcha shamlar tekshirilib, narx zonani yopgan bo'lsa `mitigated=True` bayrog'i qo'yiladi va u kelgusi skanerlashda e'tiborga olinmaydi. Bu soxta signallarni 40% ga kamaytirdi."

---

### ❓ S16: Agar loyihani yuzlab foydalanuvchilar va 50+ kripto juftliklar uchun Mass-Scale (Production) ga olib chiqish kerak bo'lsa, qanday o'zgartirishlar kiritasiz?
**💬 Javob:**
1. **Database Migration**: SQLite o'rniga **PostgreSQL** yoki **TimescaleDB** (time-series database) ga o'taman.
2. **Task Queue & Caching**: Skanerlash topshiriqlarini **Celery + Redis** yordamida tarqatilgan (distributed) workerlarga bo'lib beraman.
3. **WebSockets**: REST API o'rniga Binance/Bybit **WebSocket Stream** ga o'taman. Bu tarmoq so'rovlarini kamaytiradi va kechikishni (latency) ms darajasiga tushiradi.
4. **Containerization**: Tizimni **Docker** va **Docker Compose** orqali konteynerlashtirib, Kubernetes yoki Cloud VPS (AWS/DigitalOcean) da joylashtiraman.

---

### ❓ S17: O'zingizning ushbu loyihadagi rolgingiz va Trading/ML tajribangizni qanday baholaysiz?
**💬 Javob:**
"Men ushbu loyihada **Full-Stack Algorithmic Trading Engineer** sifatida qatnashdim:
- Financial Domain Knowledge: ICT metodologiyasi (Fair Value Gap, Order Blocks, Liquidity Sweeps, Killzones) bo'yicha chuqur tushuncham bor.
- Python & System Design: Asinxron va modular kod yozish, SQLAlchemy ORM, Telegram Bot API hamda Event-Driven arxitekturani noldan qurdim.
- Machine Learning: Feature engineering, XGBoost klassifikatsiyasi va model evaluation bo me'morligini amalga oshirdim.

Ushbu loyiha mening moliya va texnologiya (FinTech & AI) kesishmasida murakkab va real muammolarni hal qila olishimni isbotlaydi."

---
**Omadli suhbat tilaymiz! 🚀**
