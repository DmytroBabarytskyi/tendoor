# Tendoor

Tendoor (Ten + door, укр. «Тендор») — аналітика цінових аномалій публічних закупівель.

Інформаційна система, яка завантажує відкриті дані Prozorro, групує однорідні закупівлі
та виявляє аномальні цінові пропозиції методами машинного навчання, а аудитор розглядає
підозрілі лоти й фіксує вердикти.

*English.* Tendoor is an information system for screening unit prices of items in Ukrainian public
procurement (Prozorro). It makes item records comparable (pack sizes, units, CPV groups, description-based
subgroups), screens them with robust statistical and density-based rules, ranks deviations with a calibrated
classifier and explains each decision with Shapley values. The method and its evaluation are described in
the accompanying paper (`research/paper`).

## Структура

```
research/   стаття, протокол і дані розмітки, код експериментів
backend/    Python 3.12 (uv), FastAPI, SQLAlchemy + Alembic, PyMongo
frontend/   React + TypeScript + Vite
docker-compose.yml   postgres, mongo, api, worker, frontend
```

## Запуск

Уся система в Docker:

```bash
docker compose up -d --build
```

- інтерфейс: http://localhost:8080
- API та документація: http://localhost:8000/api/docs

Розробка локально (бази в Docker, код — з гарячим перезавантаженням):

```bash
docker compose up -d postgres mongo
cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn tendoor.api.app:app --reload
cd frontend && npm install && npm run dev      # http://localhost:5173
```

## Тести

```bash
cd backend && uv run pytest --cov      # інтеграційні тести створюють окрему базу tendoor_test
cd frontend && npm test                # Vitest
```

Інтеграційні тести потребують запущених PostgreSQL і MongoDB (`docker compose up -d postgres mongo`), без них
пропускаються; робочі бази не зачіпаються. CI (GitHub Actions) запускає ruff, pytest з обома базами, oxlint,
Vitest, збирання фронтенду й образів.

Навантажувальне тестування (Locust, сценарій аудитора й аналітика) — усередині мережі compose, від імені
окремого користувача з роллю «Аудитор»:

```bash
TENDOOR_LOAD_PASSWORD=... docker compose --profile loadtest run --rm --no-deps locust -u 50 -r 5 -t 3m
```

Звіт — `loadtest/results/report.html`.

## Користувачі та ролі

Ролі: **Адміністратор** (користувачі, параметри аналізу, журнал аудиту), **Аналітик** (синхронізація даних,
розширені параметри моделі), **Аудитор** (аналіз аномалій і вердикти). Першого адміністратора створює CLI —
пароль запитується інтерактивно:

```bash
docker compose exec api python -m tendoor.cli create-user --email admin@example.com --name "Адміністратор" --role admin
```

Далі користувачі створюються в інтерфейсі (розділ «Користувачі»). Зміни користувачів і параметрів фіксує
тригер БД у журналі аудиту разом з автором зміни; входи й невдалі спроби — застосунок.

## Виявлення аномальних цінових пропозицій

Розділ «Аналіз аномалій»: аудитор обирає категорії ДК 021, період і (за потреби) одиниці виміру.
Система одразу показує **індекс однорідності** вибірки — чим менший розкид категорій, тим точніша детекція.
Модель навчається на вибірці у `worker` (зазвичай до хвилини); повторний запит з тими самими даними
й параметрами повертається з кешу миттєво.

Конвеєр v2 (`backend/src/tendoor/ml/pipeline.py`):
1. **Групування.** Ієрархічні групи «одиниця + код ДК 021» (малі піднімаються до категорії та класу).
   Фасовка з опису («5 л», «180 г», «20х2 г») перераховує ціни «штук» у грн/кг чи грн/л.
2. **Семантичний поділ.** Великі групи діляться за текстом: лематизація, TF-IDF, K-Means з кількістю кластерів за силуетом.
3. **Некерований етап.** У кожній групі правило екстремумів, DBSCAN у просторі показників і модифіковане z-значення ціни.
4. **Калібратор.** Градієнтний бустинг з обмеженням монотонності (ризик не спадає зі зростанням відхилення),
   навчений на стратифікованій розмітці 400 позицій ДК 021 «15» (`ml/models/calibrator_v2.joblib`).
   Ризик-бал 0–100 — оцінка ймовірності, що перевіряльник підтвердить аномалію.
5. **Пояснення.** Внесок кожної ознаки в ризик позиції (значення Шеплі, метод Монте-Карло).

Розмітку виконано мовною моделлю за письмовим протоколом без доступу до рішень системи й перевірено людиною
на підвибірці; деталі, дані розмітки й код експериментів — у каталозі `research/`.

Параметри за замовчуванням редагує адміністратор («Параметри аналізу»);
аналітик може перевизначити їх для окремого запиту.

Оцінювання якості:
- `tendoor.ml.evaluate` — синтетичні аномалії проти 3σ та IQR;
- `tendoor.ml.experiments` — зважена стратифікована розмітка, крос-валідація калібратора,
  з параметром `--save` донавчання;
- `research/experiments` — експерименти статті (базові детектори, абляції, синтетичні помилки, пояснення).

## Синхронізація з Prozorro

Завдання виконує `worker` (фід змін Prozorro → MongoDB → PostgreSQL).

В інтерфейсі: розділ «Синхронізація» (ролі Адміністратор і Аналітик). Або через API з токеном:

```bash
curl -X POST http://localhost:8000/api/sync/jobs -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{"date_from":"2026-09-24","date_to":"2026-09-24","cpv_prefixes":["15"],"categories":["goods"]}'
```

Період задається за датою зміни документа в Prozorro (близько 25 тис. змін на добу, ~10 хв синхронізації).
Перерване завдання після перезапуску worker продовжується з того ж місця.

## Розгортання (Railway + Vercel)

Бекенд і бази — Railway, інтерфейс — Vercel. Vercel проксіює `/api/*` на Railway (`frontend/vercel.json`),
тож для браузера це одне джерело: refresh-токен лишається в httpOnly cookie першої сторони, CORS не потрібен.

**Railway** (проєкт з репозиторію GitHub):
1. Додати бази **PostgreSQL** і **MongoDB** (шаблони Railway).
2. Сервіс **api**: Root Directory `backend`, конфігурація `backend/railway.toml`. Публічний домен —
   `tendoor-api.up.railway.app`. Якщо він зайнятий, змінити його й у `frontend/vercel.json`.
3. Сервіс **worker**: той самий репозиторій і Root Directory `backend`,
   Config-as-code `/backend/railway.worker.toml`. Публічний домен не потрібен.
4. Змінні обох сервісів:

   | Змінна | Значення |
   |---|---|
   | `TENDOOR_ENV` | `production` |
   | `TENDOOR_POSTGRES_DSN` | `${{Postgres.DATABASE_URL}}` (схема `postgresql://` перетворюється на asyncpg автоматично) |
   | `TENDOOR_MONGO_URI` | `${{MongoDB.MONGO_URL}}` |
   | `TENDOOR_JWT_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `TENDOOR_COOKIE_SECURE` | `true` |
   | `FORWARDED_ALLOW_IPS` | `*` (лише api: IP клієнта з X-Forwarded-For для обмеження спроб входу) |

   Без власного секрету чи з `COOKIE_SECURE=false` застосунок у `production` не стартує.
5. Перший адміністратор: `railway ssh --service api`, далі
   `python -m tendoor.cli create-user --email ... --name ... --role admin`.

**Vercel**: імпортувати репозиторій, Root Directory `frontend`. Решту задає `vercel.json`: збирання Vite,
проксі `/api`, SPA-маршрути, заголовки безпеки.

## Ліцензія та цитування

Код поширюється за ліцензією [GNU AGPL-3.0](LICENSE): змінені версії, які надаються як мережевий сервіс,
мають публікуватися з вихідним кодом. Дані розмітки в `research/annotation` — за ліцензією CC BY 4.0.

Якщо ви використовуєте систему чи дані, посилайтеся на статтю (бібліографічний запис буде додано після
публікації препринту).
