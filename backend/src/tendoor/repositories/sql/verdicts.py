"""A3: картки лотів, вердикти аудиторів з історією, журнал перевірок, звіти."""

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tendoor.repositories.sql.access import set_actor
from tendoor.repositories.sql.models import Report, Verdict

_ITEM = """
    SELECT i.id AS item_id, i.description, i.quantity, i.unit_code, u.name AS unit_name, i.unit_price,
           i.base_unit_code, i.unit_price_base::float AS unit_price_base,
           i.quantity_base::float AS quantity_base,
           i.price_source, i.vat_included, i.cpv_code, cpv.description AS cpv_description,
           t.id AS tender_id, t.prozorro_id, t.tender_code, t.title AS tender_title, t.method_type,
           t.status AS tender_status, t.date_published, t.value_amount AS tender_value,
           pe.name AS entity_name, pe.edrpou AS entity_edrpou, pe.region AS entity_region,
           s.name AS supplier_name, s.edrpou AS supplier_edrpou, c.amount AS contract_amount
    FROM item i
    JOIN tender t ON t.id = i.tender_id
    JOIN procuring_entity pe ON pe.id = t.procuring_entity_id
    LEFT JOIN cpv ON cpv.code = i.cpv_code
    LEFT JOIN unit u ON u.code = i.unit_code
    LEFT JOIN contract c ON c.id = i.contract_id
    LEFT JOIN supplier s ON s.id = c.supplier_id
    WHERE i.id = :item
"""

_VERDICTS = """
    SELECT v.id, v.item_id, v.status, v.reason, v.comment, v.created_at, v.updated_at,
           u.email AS user_email, u.full_name AS user_name,
           i.description, i.unit_price_base::float AS unit_price_base, i.base_unit_code,
           t.tender_code, pe.name AS entity_name
    FROM verdict v
    JOIN item i ON i.id = v.item_id
    JOIN tender t ON t.id = i.tender_id
    JOIN procuring_entity pe ON pe.id = t.procuring_entity_id
    LEFT JOIN app_user u ON u.id = v.user_id
"""


class SqlVerdictRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def item_card(self, item_id: int, run_id: int | None) -> dict | None:
        """Позиція з контекстом: закупівля, замовник, постачальник; у межах запуску — оцінка та аналоги."""
        async with self._sf() as s:
            item = (await s.execute(text(_ITEM), {"item": item_id})).mappings().first()
            if item is None:
                return None
            card = {"item": dict(item), "result": None, "analogs": [], "verdict": None}
            if run_id:
                res = (
                    (
                        await s.execute(
                            text(
                                "SELECT * FROM v_anomaly_queue WHERE model_run_id = :run AND item_id = :item"
                            ),
                            {"run": run_id, "item": item_id},
                        )
                    )
                    .mappings()
                    .first()
                )
                if res:
                    card["result"] = dict(res)
                    # аналоги — звичайні пропозиції тієї ж групи, найближчі до медіани
                    card["analogs"] = [
                        dict(r)
                        for r in (
                            await s.execute(
                                text("""
                        SELECT item_id, description, unit_price_base::float AS unit_price_base,
                               quantity_base::float AS quantity_base, tender_code, entity_name,
                               entity_region, date_published
                        FROM v_anomaly_queue
                        WHERE model_run_id = :run AND category_id = :cat AND NOT is_anomaly
                          AND item_id <> :item
                        ORDER BY abs(ln(unit_price_base) - ln(:median)) LIMIT 10"""),
                                {
                                    "run": run_id,
                                    "cat": res["category_id"],
                                    "item": item_id,
                                    "median": float(res["median_price"] or 1),
                                },
                            )
                        ).mappings()
                    ]
            v = (await s.execute(text(_VERDICTS + " WHERE v.item_id = :item"), {"item": item_id})).mappings()
            card["verdict"] = next((dict(r) for r in v), None)
            return card

    async def upsert(
        self,
        actor_id: int,
        item_id: int,
        result_id: int | None,
        status: str,
        reason: str,
        comment: str | None,
    ) -> dict:
        async with self._sf() as s, s.begin():
            await set_actor(s, actor_id)
            stmt = insert(Verdict).values(
                item_id=item_id,
                anomaly_result_id=result_id,
                user_id=actor_id,
                status=status,
                reason=reason,
                comment=comment,
            )
            await s.execute(
                stmt.on_conflict_do_update(
                    index_elements=["item_id"],
                    set_={
                        "status": status,
                        "reason": reason,
                        "comment": comment,
                        "user_id": actor_id,
                        "anomaly_result_id": stmt.excluded.anomaly_result_id,
                    },
                )
            )
            row = (
                await s.execute(text(_VERDICTS + " WHERE v.item_id = :item"), {"item": item_id})
            ).mappings()
            return dict(row.one())

    async def history(self, item_id: int) -> list[dict]:
        sql = """SELECT h.id, h.old_status, h.new_status, h.old_reason, h.new_reason, h.comment, h.changed_at,
                        u.email AS user_email, u.full_name AS user_name
                 FROM verdict_history h JOIN verdict v ON v.id = h.verdict_id
                 LEFT JOIN app_user u ON u.id = h.changed_by
                 WHERE v.item_id = :item ORDER BY h.id DESC"""
        async with self._sf() as s:
            return [dict(r) for r in (await s.execute(text(sql), {"item": item_id})).mappings()]

    async def search(
        self, status: str | None, reason: str | None, user_id: int | None, limit: int, offset: int
    ) -> tuple[list[dict], int]:
        where, params = [], {"limit": limit, "offset": offset}
        for col, val in (("v.status", status), ("v.reason", reason), ("v.user_id", user_id)):
            if val is not None:
                key = col.split(".")[1]
                where.append(f"{col} = :{key}")
                params[key] = val
        cond = (" WHERE " + " AND ".join(where)) if where else ""
        async with self._sf() as s:
            total = (await s.execute(text(f"SELECT count(*) FROM verdict v{cond}"), params)).scalar()
            rows = (
                (
                    await s.execute(
                        text(_VERDICTS + cond + " ORDER BY v.updated_at DESC LIMIT :limit OFFSET :offset"),
                        params,
                    )
                )
                .mappings()
                .all()
            )
        return [dict(r) for r in rows], total

    async def stats(self) -> dict:
        async with self._sf() as s:
            rows = (
                await s.execute(
                    text("SELECT status, reason, count(*) AS n FROM verdict GROUP BY 1, 2 ORDER BY 1, 2")
                )
            ).mappings()
            return {"by_status_reason": [dict(r) for r in rows]}

    async def labels(self) -> list[dict]:
        """Розмітка для оцінювання й донавчання моделі: позиція → вердикт."""
        async with self._sf() as s:
            rows = await s.execute(
                text("SELECT item_id, status, reason FROM verdict WHERE status <> 'needs_review'")
            )
            return [dict(r) for r in rows.mappings()]

    async def log_report(self, request_id: int, user_id: int, fmt: str, n_rows: int) -> None:
        async with self._sf() as s, s.begin():
            s.add(Report(analysis_request_id=request_id, user_id=user_id, format=fmt, n_rows=n_rows))
