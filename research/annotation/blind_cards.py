"""Сліпі картки для повторної розмітки тих самих 400 позицій (стаття).

Перша розмітка бачила рішення v1 (flag, risk, stratum, медіану групи конвеєра) — мітки залежали від
методу, який оцінюють. Тут розмітник бачить лише дані закупівлі та нейтральні аналоги: позиції з тим
самим кодом ДК 021 і базовою одиницею, узяті напряму з бази (не з груп конвеєра). Порядок перемішано.

    cd backend && uv run python ../research/annotation/blind_cards.py
"""

import asyncio
import json
import random
import statistics
from pathlib import Path

import asyncpg

HERE = Path(__file__).parent
DSN = "postgresql://tendoor:tendoor@localhost:5432/tendoor"
N_ANALOGS = 8
MIN_PEERS = 5

ITEM_SQL = """
SELECT i.id, i.description, i.cpv_code, c.description AS cpv_desc, i.unit_code, u.name AS unit_name,
       i.quantity, i.unit_price, i.price_source, i.base_unit_code, i.unit_price_base,
       t.title, t.tender_code, pe.name AS entity
FROM item i
JOIN tender t ON t.id = i.tender_id
JOIN procuring_entity pe ON pe.id = t.procuring_entity_id
LEFT JOIN cpv c ON c.code = i.cpv_code
LEFT JOIN unit u ON u.code = i.unit_code
WHERE i.id = ANY($1::bigint[])
"""

PEERS_SQL = """
SELECT id, description, unit_price_base FROM item
WHERE base_unit_code = $1 AND left(cpv_code, $2) = left($3, $2) AND id <> $4 AND unit_price_base > 0
"""


def num(x):
    return None if x is None else float(x)


async def main() -> None:
    strata = json.load(open(HERE / "strata.json", encoding="utf8"))["strata"]
    ids = sorted(int(k) for k in strata)
    con = await asyncpg.connect(DSN)
    rows = await con.fetch(ITEM_SQL, ids)
    rng = random.Random(20261124)
    cards = []
    for r in rows:
        level, peers = 8, []
        for level in (8, 5, 4, 3):  # як аудитор: спершу точний код, далі ширша категорія
            peers = await con.fetch(PEERS_SQL, r["base_unit_code"], level, r["cpv_code"], r["id"])
            if len(peers) >= MIN_PEERS:
                break
        prices = [float(p["unit_price_base"]) for p in peers]
        sample = rng.sample(list(peers), min(N_ANALOGS, len(peers)))
        cards.append({
            "item_id": r["id"],
            "desc": r["description"],
            "tender_title": r["title"],
            "entity": r["entity"],
            "cpv": f"{r['cpv_code']} {r['cpv_desc'] or ''}".strip(),
            "doc_price": num(r["unit_price"]),
            "doc_unit": r["unit_name"] or r["unit_code"],
            "qty": num(r["quantity"]),
            "price_source": r["price_source"],
            "price_base": num(r["unit_price_base"]),
            "base_unit": r["base_unit_code"],
            "peers": {
                "cpv_level": level,
                "n": len(prices),
                "median": statistics.median(prices) if prices else None,
                "p10": statistics.quantiles(prices, n=10)[0] if len(prices) >= 10 else None,
                "p90": statistics.quantiles(prices, n=10)[-1] if len(prices) >= 10 else None,
                "examples": [f"{p['description'][:50]} = {float(p['unit_price_base']):.2f}" for p in sample],
            },
        })
    await con.close()
    rng.shuffle(cards)
    out = HERE / "blind_cards.json"
    json.dump(cards, open(out, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(f"cards={len(cards)} of {len(ids)} -> {out.name}")


asyncio.run(main())
