# АРХИТЕКТУРА И СПЕЦИФИКАЦИЯ: DATAPULSE AI

> **Проект:** DataPulse AI (Case 03)  
> **Клиент / Заказчик:** B2B-сервис аналитики данных «DataPulse AI»  
> **Чек проекта:** 190 000 ₽ | **Срок:** 18 дней (Дедлайн: 2026-11-29)  
> **Дедлайн MVP (80%):** 2026-11-25  
> **Тип договора:** Договор СМЗ с юр. лицом (Чек «Мой Налог», 6%)

---

## 🛠 Технологический стек
- **Frontend / UI:** Linear-Style Dark Dashboard (`#0D0E12`, `#16181D`), drag-and-drop CSV/XLSX, Chart.js / Canvas тепловая карта корреляций, чат-ассистент с карточками выбросов и медиан
- **Backend & Analytics:** Python 3.12, FastAPI, Uvicorn, Pandas, NumPy, Pydantic v2, AST (Abstract Syntax Tree) Safety Validator
- **Генерация отчетов:** fpdf2 (PDF dossiers)
- **Telegram Bot:** Aiogram 3.31 (прием таблиц CSV/XLSX и генерация PDF-отчетов)
- **Датасеты по умолчанию (4):** Titanic Survival, California Real Estate, Spotify Top Tracks, Global Retail Sales
- **Уведомления:** Пересылка аналитических запросов в Telegram `@Idrisov_prod`

---

## 🎨 Дизайн-система (Linear-Style Dark)
- **Палитра:**
  - Dark Canvas: `#0D0E12`
  - Surface Card: `#16181D`
  - Subtle Border: `#23272F`
  - Brand Violet: `#7C3AED`
  - Accent Cyan: `#06B6D4`
  - Success Emerald: `#10B981`
  - Outlier Warning Amber: `#F59E0B`
- **Макет (3 колонки):**
  - Левая: выбор датасета, инфо о строках/колонках, зона Drag & Drop.
  - Центральная: матрица корреляций, распределения, графики и таблица предпросмотра.
  - Правая: AI чат-аналитик с трансляцией вопросов в безопасные Pandas-выражения.

---

## 🏛 Архитектурная схема
```
[ Пользователь в браузере ] ───► [ Linear Dark Dashboard / Drag & Drop CSV ]
            │
            ▼
[ FastAPI /api/query ] ────────► [ AST Safety Parser ] ──► [ Pandas Engine ]
                                                                 │
[ Пользователь в Telegram ] ───► [ Aiogram Bot (CSV/XLSX) ] ──────┤
                                                                 ▼
                                                        [ fpdf2 PDF Report ]
```

---

## 🔐 Переменные окружения (.env.example)
```env
BOT_TOKEN=8217851677:AAHN34TMuC1P4e6SppuazFN8BIiLHa_RyIc
ADMIN_CHAT_ID=1387913438
OWNER_HANDLE=@Idrisov_prod
WEB_PORT=8003
DATASETS_DIR=data/datasets/
REPORTS_DIR=data/reports/
```

---

## 🔗 Ресурсы и ссылки
- **Web App:** `http://localhost:8003/`
- **Telegram Bot:** `@DataPulseAIBot`
- **GitHub:** `https://github.com/Website-for-everyone/Case03_DataPulseAI`
