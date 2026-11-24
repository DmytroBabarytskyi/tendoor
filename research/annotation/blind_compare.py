"""Узгодженість сліпої розмітки зі старою (розмітник бачив рішення v1) і зсув, який дало знання рішення."""
import collections
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import glob
import json

from sklearn.metrics import cohen_kappa_score


def load(pattern):
    d = {}
    for f in sorted(glob.glob(pattern)):
        for k, v in json.load(open(f, encoding="utf8")).items():
            d[int(k)] = "not_anomaly" if v[0] == "false_positive" else v[0]
    return d


old = load("decisions*.json")
new = load("blind_decisions_*.json")
strata = {int(k): v for k, v in json.load(open("strata.json", encoding="utf8"))["strata"].items()}
cards = {c["item_id"]: c for f in ("review_cards.json", "review_cards2.json") for c in json.load(open(f, encoding="utf8"))}
ids = sorted(set(old) & set(new))
print("спільних:", len(ids))
both = [i for i in ids if old[i] != "needs_review" and new[i] != "needs_review"]
y_old = [old[i] == "confirmed" for i in both]
y_new = [new[i] == "confirmed" for i in both]
print(f"κ (бінарно, без needs_review, n={len(both)}): {cohen_kappa_score(y_old, y_new):.3f}")
print(f"κ (3 класи, n={len(ids)}): {cohen_kappa_score([old[i] for i in ids], [new[i] for i in ids]):.3f}")
print("матриця (стара → сліпа):", dict(collections.Counter((old[i], new[i]) for i in ids)))
for s in ("top", "mid", "normal"):
    sub = [i for i in ids if strata[i] == s]
    co = sum(old[i] == "confirmed" for i in sub)
    cn = sum(new[i] == "confirmed" for i in sub)
    print(f"{s:6} n={len(sub):3}  підтверджено: стара {co:3} ({co/len(sub):.0%})  сліпа {cn:3} ({cn/len(sub):.0%})")
# де стара і сліпа розходяться — чи збігається це з рішенням v1
flip = collections.Counter()
for i in ids:
    if (old[i] == "confirmed") != (new[i] == "confirmed"):
        flip[("v1 позначила" if cards[i]["flag"] else "v1 не позначила", "стара=так" if old[i] == "confirmed" else "стара=ні")] += 1
print("розбіжності за рішенням v1:", dict(flip))
