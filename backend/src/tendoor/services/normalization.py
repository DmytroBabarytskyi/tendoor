"""Перетворення сирого документа тендера Prozorro (API 2.5) у нормалізовані записи Silver.

Чиста функція без доступу до БД: вхід — dict із tenders_raw.data, вихід — NormalizedTender.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

# ---------------------------------------------------------------- результат


@dataclass(slots=True)
class EntityRec:
    edrpou: str
    name: str
    region: str | None = None
    kind: str | None = None


@dataclass(slots=True)
class CpvRec:
    code: str  # 8 цифр без контрольної
    description: str | None
    level: int
    parent_code: str | None


@dataclass(slots=True)
class LotRec:
    prozorro_lot_id: str
    title: str | None
    value_amount: Decimal | None
    status: str | None


@dataclass(slots=True)
class ContractRec:
    prozorro_contract_id: str
    prozorro_lot_id: str | None
    supplier: EntityRec | None
    status: str
    amount: Decimal | None
    vat_included: bool | None
    date_signed: datetime | None


@dataclass(slots=True)
class ItemRec:
    prozorro_item_id: str
    prozorro_lot_id: str | None
    prozorro_contract_id: str | None
    cpv_code: str | None
    unit_code: str | None
    unit_name: str | None
    description: str
    description_clean: str
    quantity: Decimal | None
    unit_price: Decimal | None
    price_source: str | None  # unit_value | contract | expected
    vat_included: bool | None


@dataclass(slots=True)
class NormalizedTender:
    prozorro_id: str
    tender_code: str
    title: str | None
    method_type: str
    category: str | None
    status: str
    date_published: datetime
    date_modified: datetime
    value_amount: Decimal | None
    currency: str
    vat_included: bool | None
    entity: EntityRec
    lots: list[LotRec] = field(default_factory=list)
    contracts: list[ContractRec] = field(default_factory=list)
    items: list[ItemRec] = field(default_factory=list)
    cpvs: dict[str, CpvRec] = field(default_factory=dict)


# ---------------------------------------------------------------- CPV


def cpv_digits(code: str | None) -> str | None:
    """'15311100-4' -> '15311100'; некоректні коди відкидаються."""
    if not code:
        return None
    digits = code.split("-", 1)[0].strip()
    return digits if len(digits) == 8 and digits.isdigit() else None


def cpv_level(code: str) -> int:
    """1 — розділ (XX000000), 2 — група, 3 — клас, 4 — категорія, 5 — підкатегорія."""
    significant = len(code.rstrip("0"))
    return max(1, min(5, significant - 1))


def cpv_parent(code: str) -> str | None:
    significant = code.rstrip("0")
    if len(significant) <= 2:
        return None
    parent = significant[:-1].rstrip("0")
    parent = parent if len(parent) >= 2 else significant[:2]
    return parent.ljust(8, "0")


def cpv_chain(code: str, description: str | None) -> list[CpvRec]:
    """Код разом з усіма предками — щоб FK parent_code завжди мав куди посилатися."""
    chain = [CpvRec(code, description, cpv_level(code), cpv_parent(code))]
    parent = cpv_parent(code)
    while parent:
        chain.append(CpvRec(parent, None, cpv_level(parent), cpv_parent(parent)))
        parent = cpv_parent(parent)
    return chain


# ---------------------------------------------------------------- очищення тексту

_LATIN_TO_CYR = str.maketrans("aceiopxyACEIOPXYKMHTB", "асеіорхуАСЕІОРХУКМНТВ")
_RE_DK = re.compile(r"(дк|dk)\s*0?21\s*[:\-]?\s*2015", re.IGNORECASE)
_RE_CPV = re.compile(r"\b\d{8}-\d\b|\b\d{8}\b")
_RE_NOISE = re.compile(r"[^0-9a-zа-яіїєґ'’ ]+")
_STOP = {
    "код",
    "за",
    "згідно",
    "cpv",
    "єзс",
    "єдиний",
    "закупівельний",
    "словник",
    "лот",
    "та",
    "з",
    "і",
    "й",
}


def _fix_mixed_word(word: str) -> str:
    """Латинські двійники літер замінюються лише в словах, де вже є кирилиця."""
    if re.search(r"[а-яіїєґ]", word, re.IGNORECASE) and re.search(r"[a-z]", word, re.IGNORECASE):
        return word.translate(_LATIN_TO_CYR)
    return word


def clean_description(text: str) -> str:
    text = _RE_DK.sub(" ", text)
    text = _RE_CPV.sub(" ", text)
    text = " ".join(_fix_mixed_word(w) for w in text.split())
    text = _RE_NOISE.sub(" ", text.lower())
    words = [w for w in text.split() if w not in _STOP and len(w) > 1]
    return " ".join(words)


# ---------------------------------------------------------------- допоміжне


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _entity(party: dict | None) -> EntityRec | None:
    if not party:
        return None
    ident = party.get("identifier") or {}
    edrpou = str(ident.get("id") or "").strip()
    if not edrpou:
        return None
    name = ident.get("legalName") or party.get("name") or edrpou
    return EntityRec(
        edrpou=edrpou, name=name, region=(party.get("address") or {}).get("region"), kind=party.get("kind")
    )


# ---------------------------------------------------------------- основна функція


def normalize_tender(doc: dict) -> NormalizedTender:
    value = doc.get("value") or {}
    entity = _entity(doc.get("procuringEntity")) or EntityRec(edrpou="unknown", name="Невідомий замовник")

    nt = NormalizedTender(
        prozorro_id=doc["id"],
        tender_code=doc.get("tenderID", doc["id"]),
        title=doc.get("title"),
        method_type=doc.get("procurementMethodType", "unknown"),
        category=doc.get("mainProcurementCategory"),
        status=doc.get("status", "unknown"),
        # «date» змінюється разом зі статусом, тому момент оголошення — dateCreated
        date_published=_dt(doc.get("dateCreated") or doc.get("date")),
        date_modified=_dt(doc["dateModified"]),
        value_amount=_dec(value.get("amount")),
        currency=value.get("currency") or "UAH",
        vat_included=value.get("valueAddedTaxIncluded"),
        entity=entity,
    )

    for lot in doc.get("lots") or []:
        nt.lots.append(
            LotRec(
                lot["id"], lot.get("title"), _dec((lot.get("value") or {}).get("amount")), lot.get("status")
            )
        )
    lot_values = {lot.prozorro_lot_id: lot.value_amount for lot in nt.lots}

    awards = {a["id"]: a for a in doc.get("awards") or []}
    for c in doc.get("contracts") or []:
        award = awards.get(c.get("awardID")) or {}
        cval = c.get("value") or {}
        nt.contracts.append(
            ContractRec(
                prozorro_contract_id=c["id"],
                prozorro_lot_id=award.get("lotID"),
                supplier=_entity((award.get("suppliers") or c.get("suppliers") or [None])[0]),
                status=c.get("status", "unknown"),
                amount=_dec(cval.get("amount")),
                vat_included=cval.get("valueAddedTaxIncluded"),
                date_signed=_dt(c.get("dateSigned")),
            )
        )
    # діючий договір на лот (None — для тендера без лотів)
    active = {c.prozorro_lot_id: c for c in nt.contracts if c.status == "active"}

    items = doc.get("items") or []
    per_lot: dict[str | None, int] = {}
    for it in items:
        per_lot[it.get("relatedLot")] = per_lot.get(it.get("relatedLot"), 0) + 1

    for it in items:
        lot_id = it.get("relatedLot")
        unit = it.get("unit") or {}
        cls = it.get("classification") or {}
        code = cpv_digits(cls.get("id")) if cls.get("scheme", "ДК021") in ("ДК021", "CPV") else None
        if code:
            for rec in cpv_chain(code, cls.get("description")):
                known = nt.cpvs.get(rec.code)
                if known is None or (known.description is None and rec.description):
                    nt.cpvs[rec.code] = rec
        qty = _dec(it.get("quantity"))
        contract = active.get(lot_id)

        price, source, vat = None, None, None
        uval = unit.get("value") or {}
        if _dec(uval.get("amount")) is not None:
            price, source, vat = _dec(uval["amount"]), "unit_value", uval.get("valueAddedTaxIncluded")
        elif qty and qty > 0 and per_lot[lot_id] == 1:
            # ціну за одиницю можна вивести лише для однопозиційного лота
            if contract and contract.amount:
                price, source, vat = contract.amount / qty, "contract", contract.vat_included
            else:
                expected = lot_values.get(lot_id) if lot_id else nt.value_amount
                if expected:
                    price, source, vat = expected / qty, "expected", nt.vat_included

        description = (it.get("description") or cls.get("description") or "").strip()
        nt.items.append(
            ItemRec(
                prozorro_item_id=it.get("id") or f"idx{len(nt.items)}",
                prozorro_lot_id=lot_id,
                prozorro_contract_id=contract.prozorro_contract_id if contract else None,
                cpv_code=code,
                unit_code=(unit.get("code") or "").strip() or None,
                unit_name=unit.get("name"),
                description=description,
                description_clean=clean_description(description),
                quantity=qty,
                unit_price=price.quantize(Decimal("0.000001")) if price is not None else None,
                price_source=source,
                vat_included=vat,
            )
        )
    return nt


def matches_filter(doc: dict, cpv_prefixes: list[str], categories: list[str]) -> bool:
    """Чи потрапляє тендер у вибірку синхронізації (порожній фільтр — без обмежень)."""
    if categories and doc.get("mainProcurementCategory") not in categories:
        return False
    if not cpv_prefixes:
        return True
    for it in doc.get("items") or []:
        code = cpv_digits((it.get("classification") or {}).get("id"))
        if code and any(code.startswith(p) for p in cpv_prefixes):
            return True
    return False
