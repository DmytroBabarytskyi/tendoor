"""Вибірка для людської перевірки сліпої розмітки та офлайн-сторінка для неї.

80 позицій: 30 підтверджених і 50 не аномальних за сліпою розміткою LLM (рішення розмітника приховане).
Людина бачить ті самі сліпі картки. Результат — human_labels.json (кнопка на сторінці).

    python human_check.py  →  human_check.html, human_sample.json
"""

import glob
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
cards = {c["item_id"]: c for c in json.load(open(HERE / "blind_cards.json", encoding="utf8"))}
dec = {}
for f in sorted(glob.glob(str(HERE / "blind_decisions_*.json"))):
    dec.update({int(k): v[0] for k, v in json.load(open(f, encoding="utf8")).items()})

rng = random.Random(80)
pos = sorted(i for i, s in dec.items() if s == "confirmed")
neg = sorted(i for i, s in dec.items() if s == "not_anomaly")
sample = rng.sample(pos, 30) + rng.sample(neg, 50)
rng.shuffle(sample)
json.dump(sample, open(HERE / "human_sample.json", "w", encoding="utf8"))


def card_view(c: dict) -> dict:
    p = c["peers"]
    return {
        "id": c["item_id"], "desc": c["desc"], "title": c["tender_title"], "entity": c["entity"],
        "cpv": c["cpv"], "doc_price": c["doc_price"], "doc_unit": c["doc_unit"], "qty": c["qty"],
        "price_base": c["price_base"], "base_unit": c["base_unit"], "n": p["n"], "median": p["median"],
        "p10": p["p10"], "p90": p["p90"], "examples": p["examples"],
    }


data = json.dumps([card_view(cards[i]) for i in sample], ensure_ascii=False).replace("</", "<\\/")
html = (HERE / "human_check.template.html").read_text(encoding="utf8").replace("__DATA__", data)
(HERE / "human_check.html").write_text(html, encoding="utf8")
print(f"вибірка {len(sample)} → human_check.html")
