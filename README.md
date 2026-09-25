# Tendoor

Tendoor (Ten + door, укр. «Тендор») — аналітика цінових аномалій публічних закупівель.

Інформаційна система, яка завантажує відкриті дані Prozorro, групує однорідні закупівлі
та виявляє аномальні цінові пропозиції методами машинного навчання, а аудитор розглядає
підозрілі лоти й фіксує вердикти.

## Структура

```
backend/    Python 3.12 (uv), FastAPI, SQLAlchemy + Alembic, PyMongo
frontend/   React + TypeScript + Vite
docker-compose.yml   postgres, mongo, api, frontend
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

Перевірки бекенду: `uv run pytest`, `uv run ruff check .`
