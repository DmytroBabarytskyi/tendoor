"""Навантажувальне тестування Tendoor (Locust).

Сценарій — типова робота аудитора з результатами аналізу: запит з тими самими умовами береться з кешу,
далі перегляд черги аномалій, карток позицій з аналогами, груп і діаграм. Окремий клас імітує
аналітика, який переглядає вибірки перед запуском (попередній перегляд і пошук кодів ДК 021).

Запуск усередині мережі compose (проксі портів Docker Desktop на Windows обриває сплески з'єднань,
тож запуск з хоста вимірює його, а не систему):

  TENDOOR_LOAD_PASSWORD=... docker compose --profile loadtest run --rm --no-deps locust -u 50 -r 5 -t 3m

Результати — loadtest/results (CSV і HTML-звіт).
Облікові дані — змінні TENDOOR_LOAD_EMAIL / TENDOOR_LOAD_PASSWORD (окремий користувач з роллю auditor).
Вибірка — TENDOOR_LOAD_CPV (за замовчуванням 15) за серпень–вересень 2026; модель для неї вже навчена,
тож тест вимірює роботу API й бази, а не навчання (навчання вимірюється окремо: до 1 хв).
"""

import os
import random

from locust import HttpUser, between, events, task

EMAIL = os.environ.get("TENDOOR_LOAD_EMAIL", "loadtest@tendoor.dev")
PASSWORD = os.environ.get("TENDOOR_LOAD_PASSWORD", "")
SELECTION = {
    "cpv_prefixes": [os.environ.get("TENDOOR_LOAD_CPV", "15")],
    "date_from": "2026-08-01",
    "date_to": "2026-09-30",
    "unit_codes": [],
}


@events.test_start.add_listener
def _check(environment, **_):
    if not PASSWORD:
        raise SystemExit("Задайте TENDOOR_LOAD_PASSWORD")


class TendoorUser(HttpUser):
    abstract = True
    wait_time = between(1, 3)  # «час на обдумування» між діями людини

    def on_start(self) -> None:
        r = self.client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, name="auth/login")
        r.raise_for_status()
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"


class Auditor(TendoorUser):
    weight = 4

    def on_start(self) -> None:
        super().on_start()
        # ті самі умови й параметри, що вже аналізувалися, — результат з кешу, без черги
        r = self.client.post("/api/analysis/requests", json=SELECTION, name="analysis/requests [cache]")
        r.raise_for_status()
        req = r.json()
        assert req["from_cache"] and req["status"] == "done", req
        self.request_id = req["id"]
        self.run_id = req["model_run_id"]
        base = f"/api/analysis/requests/{self.request_id}"
        self.categories = [
            c["id"]
            for c in self.client.get(f"{base}/categories", name="analysis/categories").json()
            if c["analysed"] and c["n_anomalies"]
        ]
        self.items = [
            a["item_id"]
            for a in self.client.get(f"{base}/anomalies?limit=200", name="analysis/anomalies").json()["items"]
        ]

    @task(5)
    def anomaly_queue(self) -> None:
        offset = random.choice([0, 50, 100, 150])
        self.client.get(
            f"/api/analysis/requests/{self.request_id}/anomalies?limit=50&offset={offset}",
            name="analysis/anomalies",
        )

    @task(4)
    def item_card(self) -> None:
        item = random.choice(self.items)
        self.client.get(f"/api/items/{item}?run_id={self.run_id}", name="items/{id}")
        self.client.get(f"/api/items/{item}/verdict-history", name="items/{id}/verdict-history")

    @task(2)
    def group_charts(self) -> None:
        cat = random.choice(self.categories)
        base = f"/api/analysis/requests/{self.request_id}"
        self.client.get(f"{base}/anomalies?category_id={cat}&only_anomalies=false", name="analysis/anomalies?category")
        self.client.get(f"{base}/points?category_id={cat}", name="analysis/points")

    @task(1)
    def overview(self) -> None:
        self.client.get("/api/analysis/requests", name="analysis/requests")
        self.client.get("/api/verdicts/stats", name="verdicts/stats")
        self.client.get("/api/procurement/stats", name="procurement/stats")


class Analyst(TendoorUser):
    """Підготовка вибірки: пошук кодів і попередній перегляд однорідності (агрегати по всій базі)."""

    weight = 1

    @task(3)
    def cpv_search(self) -> None:
        q = random.choice(["молоко", "хліб", "олія", "м'ясо", "овочі", "1553", "0322"])
        self.client.get(f"/api/analysis/cpv?q={q}", name="analysis/cpv")

    @task(1)
    def preview(self) -> None:
        cpv = random.choice(["15", "155", "1581", "03"])
        self.client.post(
            "/api/analysis/preview",
            json={**SELECTION, "cpv_prefixes": [cpv]},
            name="analysis/preview",
        )
