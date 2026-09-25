# Tendoor

Tendoor (Ten + door, укр. «Тендор») — аналітика цінових аномалій публічних закупівель.

Інформаційна система, яка завантажує відкриті дані Prozorro, групує однорідні закупівлі
та виявляє аномальні цінові пропозиції методами машинного навчання, а аудитор розглядає
підозрілі лоти й фіксує вердикти.

## Структура

```
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

Перевірки бекенду: `uv run pytest` (інтеграційні тести потребують запущеного Postgres), `uv run ruff check .`

## Синхронізація з Prozorro

Завдання ставиться через API, виконує його `worker` (фід змін Prozorro → MongoDB → PostgreSQL):

```bash
curl -X POST http://localhost:8000/api/sync/jobs -H "Content-Type: application/json"   -d '{"date_from":"2026-09-24","date_to":"2026-09-24","cpv_prefixes":["15"],"categories":["goods"]}'
curl http://localhost:8000/api/sync/jobs/1          # прогрес
curl http://localhost:8000/api/procurement/stats    # що вже в базі
```

Період задається за датою зміни документа в Prozorro (близько 25 тис. змін на добу, ~10 хв синхронізації).
Перерване завдання після перезапуску worker продовжується з того ж місця.
