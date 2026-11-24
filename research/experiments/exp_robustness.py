"""Experiment 4: robustness of the annotated-data results, from saved per-item scores (no pipeline run).

    python exp_robustness.py [blind|adjusted]
        reads results/scores_<kind>.csv; writes results/robustness.csv (blind) or robustness_adjusted.csv,
        and, for blind labels, results/reliability.csv

1. Stratified bootstrap of the AP gain of the calibrated model over every other method, including the
   best baseline (3-sigma rule). Predictions are fixed (nested-CV scores); the intervals therefore do not
   include the variance of refitting the model.
2. Sensitivity to the single confirmed item of the unflagged stratum (weight N_h/n_h ~ 60): AP with and
   without it.
3. Reliability of the calibrated scores: weighted observed rate per score bin and the weighted Brier score.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

RES = Path(__file__).resolve().parent / "results"
METHODS = ["sigma3", "iforest_groups", "v1", "screening_v2", "calibrator", "hybrid"]


def ap(t: pd.DataFrame, col: str) -> float:
    return average_precision_score(t["y"], t[col].fillna(-1e9), sample_weight=t["weight"])


KIND = sys.argv[1] if len(sys.argv) > 1 else "blind"


def main() -> None:
    t = pd.read_csv(RES / f"scores_{KIND}.csv")
    rows = []
    rng = np.random.default_rng(0)
    groups = [np.flatnonzero(t["stratum"].to_numpy() == s) for s in t["stratum"].unique()]
    boots = {m: [] for m in METHODS}
    for _ in range(2000):
        idx = np.concatenate([rng.choice(g, len(g), replace=True) for g in groups])
        b = t.iloc[idx]
        for m in METHODS:
            boots[m].append(ap(b, m))
    cal = np.array(boots["calibrator"])
    normal_pos = t[(t["stratum"] == "normal") & (t["y"] == 1)]
    without = t.drop(normal_pos.index)
    for m in METHODS:
        d = cal - np.array(boots[m])
        rows.append({
            "method": m,
            "ap": ap(t, m),
            "ap_without_normal_positive": ap(without, m),
            "calibrator_gain_mean": d.mean() if m != "calibrator" else np.nan,
            "calibrator_gain_lo": np.percentile(d, 2.5) if m != "calibrator" else np.nan,
            "calibrator_gain_hi": np.percentile(d, 97.5) if m != "calibrator" else np.nan,
            "p_gain_le_0": (d <= 0).mean() if m != "calibrator" else np.nan,
        })
    out = pd.DataFrame(rows).set_index("method")
    share = (normal_pos["weight"] * normal_pos["y"]).sum() / (t["weight"] * t["y"]).sum()
    print(f"normal-stratum positives: {list(normal_pos['item_id'])}, share of weighted positives {share:.3f}")
    print(out.round(3).to_string())
    out.round(4).to_csv(RES / ("robustness.csv" if KIND == "blind" else f"robustness_{KIND}.csv"))

    # hybrid vs calibrator: dependence on extremes of the unflagged stratum that the annotation rejects
    neg_ext = t[(t["stratum"] == "normal") & (t["y"] == 0) & (t["hybrid"] >= 1)]
    rest = t.drop(neg_ext.index)
    print(f"normal-stratum extremes labelled negative: {list(neg_ext['item_id'])}; "
          f"AP without them: calibrator {ap(rest, 'calibrator'):.3f}, hybrid {ap(rest, 'hybrid'):.3f}")
    if KIND != "blind":
        return

    # reliability of the calibrated scores (nested-CV out-of-fold)
    p, y, w = t["calibrator"].to_numpy(), t["y"].to_numpy(), t["weight"].to_numpy()
    bins = np.array([0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0001])
    rel = []
    for lo, hi in zip(bins[:-1], bins[1:], strict=True):
        m = (p >= lo) & (p < hi)
        if m.any():
            rel.append({"bin": f"{lo:.1f}-{min(hi, 1):.1f}", "n": int(m.sum()), "mean_score": np.average(p[m], weights=w[m]),
                        "observed_rate": np.average(y[m], weights=w[m])})
    rel = pd.DataFrame(rel)
    brier = np.average((p - y) ** 2, weights=w)
    print(rel.round(3).to_string(index=False))
    print(f"weighted Brier score {brier:.4f}; weighted base rate {np.average(y, weights=w):.4f}")
    rel.round(4).to_csv(RES / "reliability.csv", index=False)


if __name__ == "__main__":
    main()
