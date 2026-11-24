"""Узгодженість людини зі сліпою LLM-розміткою на вибірці human_sample.json.

    python human_agreement.py [шлях до human_labels.json]
"""

import collections
import glob
import json
import sys
from pathlib import Path

from sklearn.metrics import cohen_kappa_score

HERE = Path(__file__).parent
human = {int(k): v for k, v in json.load(open(sys.argv[1] if len(sys.argv) > 1 else HERE / "human_labels.json",
                                               encoding="utf8")).items()}
llm = {}
for f in sorted(glob.glob(str(HERE / "blind_decisions_*.json"))):
    llm.update({int(k): v[0] for k, v in json.load(open(f, encoding="utf8")).items()})
sample = json.load(open(HERE / "human_sample.json", encoding="utf8"))
done = [i for i in sample if i in human]
print(f"відповідей: {len(done)} з {len(sample)}")
both = [i for i in done if human[i] != "needs_review"]
h = [human[i] == "confirmed" for i in both]
m = [llm[i] == "confirmed" for i in both]
agree = sum(a == b for a, b in zip(h, m)) / len(both)
print(f"бінарно (без «не можу судити», n={len(both)}): збіг {agree:.1%}, κ = {cohen_kappa_score(h, m):.3f}")
print("матриця (людина, LLM):", dict(collections.Counter((human[i], llm[i]) for i in done)))
for i in done:
    if (human[i] == "confirmed") != (llm[i] == "confirmed") and human[i] != "needs_review":
        print("  розбіжність:", i, "людина:", human[i], "LLM:", llm[i])
