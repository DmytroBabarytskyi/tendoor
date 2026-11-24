"""Перенавчання калібратора на сліпій розмітці (без зсуву від рішень v1).

    cd backend && uv run python ../research/experiments/train_blind.py [blind|adjusted]

Модель зберігається в results/calibrator_<kind>.joblib; розгорнута модель застосунку не змінюється.
Поріг — максимум зваженого F1 на відкладених фолдах (5 фолдів × 5 повторів).
"""

import sys

import numpy as np
from common import OUT, _best_threshold, load_labels, load_selection, stratum_weights
from sklearn.model_selection import StratifiedKFold

from tendoor.ml.calibration import FEATURES, Calibrator
from tendoor.ml.pipeline import DetectionParams, run_detection

KIND = sys.argv[1] if len(sys.argv) > 1 else "blind"


def main() -> None:
    df = load_selection()
    lab = load_labels(KIND)
    w = stratum_weights(lab)
    items = run_detection(df, DetectionParams(calibrate=False)).items.set_index("item_id")
    lab = lab.join(items, on="item_id")
    ok = lab["risk"].notna().to_numpy()
    sub, wsub = lab[ok].reset_index(drop=True), w[ok]
    y = sub["y"].to_numpy()
    oof = np.zeros((5, len(sub)))
    for rep in range(5):
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=rep).split(sub, y):
            oof[rep, te] = Calibrator.fit(sub.iloc[tr], y[tr], random_state=rep).predict_proba(sub.iloc[te])
    threshold = _best_threshold(y, oof.mean(0), wsub)
    cal = Calibrator.fit(sub, y, meta={
        "version": f"v2-2-{KIND}",
        "trained_on": "CPV 15, 01.08–30.09.2026, сліпа розмітка" + (" + людська перевірка" if KIND == "adjusted" else ""),
        "n_labels": int(len(sub)), "n_positive": int(y.sum()), "threshold": threshold, "features": FEATURES,
    })
    path = OUT / f"calibrator_{KIND}.joblib"
    cal.save(path)
    print(f"збережено {path.name}: міток {len(sub)}, підтверджено {y.sum()}, поріг {threshold:.2f}")


if __name__ == "__main__":
    main()
