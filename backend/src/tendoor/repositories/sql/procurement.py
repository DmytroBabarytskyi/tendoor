"""Збереження нормалізованих закупівель (Silver) у PostgreSQL."""

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tendoor.repositories.sql.models import (
    Contract,
    Cpv,
    Item,
    Lot,
    ProcuringEntity,
    Supplier,
    Tender,
    Unit,
)
from tendoor.services.normalization import EntityRec, NormalizedTender


def _upsert(model, rows: list[dict], keys: list[str], update: list[str]):
    # ON CONFLICT не допускає двох рядків з однаковим ключем в одному INSERT — лишаємо останній
    rows = list({tuple(r[k] for k in keys): r for r in rows}.values())
    stmt = insert(model).values(rows)
    return stmt.on_conflict_do_update(index_elements=keys, set_={c: stmt.excluded[c] for c in update})


class SqlProcurementRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def save_tenders(self, tenders: list[NormalizedTender]) -> int:
        if not tenders:
            return 0
        async with self._sf() as s, s.begin():
            await self._save_references(s, tenders)
            for nt in tenders:
                await self._save_one(s, nt)
        return len(tenders)

    async def _save_references(self, s: AsyncSession, tenders: list[NormalizedTender]) -> None:
        # Невідомі одиниці стають власними базовими (множник 1), назва — з даних Prozorro
        units = {i.unit_code: i.unit_name or i.unit_code for t in tenders for i in t.items if i.unit_code}
        if units:
            rows = [{"code": c, "name": n[:60], "base_code": c, "factor": 1} for c, n in units.items()]
            await s.execute(insert(Unit).values(rows).on_conflict_do_nothing(index_elements=["code"]))

        cpvs: dict[str, dict] = {}
        for t in tenders:
            for rec in t.cpvs.values():
                known = cpvs.get(rec.code)
                if known is None or (known["description"] is None and rec.description):
                    cpvs[rec.code] = {
                        "code": rec.code,
                        "parent_code": rec.parent_code,
                        "description": rec.description,
                        "level": rec.level,
                    }
        if cpvs:
            # предки вставляються раніше за нащадків — FK parent_code задоволено
            rows = sorted(cpvs.values(), key=lambda r: r["level"])
            stmt = insert(Cpv).values(rows)
            await s.execute(
                stmt.on_conflict_do_update(
                    index_elements=["code"],
                    set_={"description": func.coalesce(stmt.excluded.description, Cpv.description)},
                )
            )

    async def _entity_id(self, s: AsyncSession, model, e: EntityRec) -> int:
        row = {"edrpou": e.edrpou, "name": e.name}
        update = ["name"]
        if model is ProcuringEntity:
            row |= {"region": e.region, "kind": e.kind}
            update += ["region", "kind"]
        return (await s.execute(_upsert(model, [row], ["edrpou"], update).returning(model.id))).scalar_one()

    async def _save_one(self, s: AsyncSession, nt: NormalizedTender) -> None:
        entity_id = await self._entity_id(s, ProcuringEntity, nt.entity)
        tender_row = {
            "prozorro_id": nt.prozorro_id,
            "tender_code": nt.tender_code,
            "procuring_entity_id": entity_id,
            "title": nt.title,
            "method_type": nt.method_type,
            "category": nt.category,
            "status": nt.status,
            "date_published": nt.date_published,
            "value_amount": nt.value_amount,
            "currency": nt.currency,
            "vat_included": nt.vat_included,
            "date_modified": nt.date_modified,
        }
        tender_id = (
            await s.execute(
                _upsert(
                    Tender, [tender_row], ["prozorro_id"], [k for k in tender_row if k != "prozorro_id"]
                ).returning(Tender.id)
            )
        ).scalar_one()

        lot_ids: dict[str, int] = {}
        if nt.lots:
            rows = [
                {
                    "tender_id": tender_id,
                    "prozorro_lot_id": lt.prozorro_lot_id,
                    "title": lt.title,
                    "value_amount": lt.value_amount,
                    "status": lt.status,
                }
                for lt in nt.lots
            ]
            res = await s.execute(
                _upsert(
                    Lot, rows, ["tender_id", "prozorro_lot_id"], ["title", "value_amount", "status"]
                ).returning(Lot.prozorro_lot_id, Lot.id)
            )
            lot_ids = dict(res.all())
        await s.execute(
            delete(Lot).where(Lot.tender_id == tender_id, Lot.prozorro_lot_id.not_in(list(lot_ids) or [""]))
        )

        contract_ids: dict[str, int] = {}
        if nt.contracts:
            rows = []
            for c in nt.contracts:
                supplier_id = await self._entity_id(s, Supplier, c.supplier) if c.supplier else None
                rows.append(
                    {
                        "tender_id": tender_id,
                        "lot_id": lot_ids.get(c.prozorro_lot_id),
                        "supplier_id": supplier_id,
                        "prozorro_contract_id": c.prozorro_contract_id,
                        "status": c.status,
                        "amount": c.amount,
                        "vat_included": c.vat_included,
                        "date_signed": c.date_signed,
                    }
                )
            res = await s.execute(
                _upsert(
                    Contract,
                    rows,
                    ["tender_id", "prozorro_contract_id"],
                    ["lot_id", "supplier_id", "status", "amount", "vat_included", "date_signed"],
                ).returning(Contract.prozorro_contract_id, Contract.id)
            )
            contract_ids = dict(res.all())
        await s.execute(
            delete(Contract).where(
                Contract.tender_id == tender_id,
                Contract.prozorro_contract_id.not_in(list(contract_ids) or [""]),
            )
        )

        item_keys = [i.prozorro_item_id for i in nt.items]
        if nt.items:
            rows = [
                {
                    "tender_id": tender_id,
                    "lot_id": lot_ids.get(i.prozorro_lot_id),
                    "contract_id": contract_ids.get(i.prozorro_contract_id),
                    "prozorro_item_id": i.prozorro_item_id,
                    "cpv_code": i.cpv_code,
                    "unit_code": i.unit_code,
                    "description": i.description,
                    "description_clean": i.description_clean,
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "price_source": i.price_source,
                    "vat_included": i.vat_included,
                }
                for i in nt.items
            ]
            cols = [k for k in rows[0] if k not in ("tender_id", "prozorro_item_id")]
            await s.execute(_upsert(Item, rows, ["tender_id", "prozorro_item_id"], cols))
        await s.execute(
            delete(Item).where(Item.tender_id == tender_id, Item.prozorro_item_id.not_in(item_keys or [""]))
        )

    async def stats(self) -> dict:
        async with self._sf() as s:
            totals = (
                (
                    await s.execute(
                        text("""
                SELECT (SELECT count(*) FROM tender)            AS tenders,
                       (SELECT count(*) FROM item)              AS items,
                       (SELECT count(*) FROM item WHERE unit_price IS NOT NULL) AS items_priced,
                       (SELECT count(*) FROM procuring_entity)  AS entities,
                       (SELECT min(date_published) FROM tender) AS date_min,
                       (SELECT max(date_published) FROM tender) AS date_max
            """)
                    )
                )
                .mappings()
                .one()
            )
            by_source = (
                await s.execute(select(Item.price_source, func.count()).group_by(Item.price_source))
            ).all()
            top_units = (
                (
                    await s.execute(
                        text("""
                SELECT i.base_unit_code AS code, u.name, count(*) AS n
                FROM item i LEFT JOIN unit u ON u.code = i.base_unit_code
                WHERE i.unit_price IS NOT NULL
                GROUP BY 1, 2 ORDER BY n DESC LIMIT 10
            """)
                    )
                )
                .mappings()
                .all()
            )
        return {
            **dict(totals),
            "by_price_source": {str(k): v for k, v in by_source},
            "top_units": [dict(r) for r in top_units],
        }
