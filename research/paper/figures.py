"""Figures for the paper. Reads the CSV tables in ../experiments/results; runs nothing itself.

    python figures.py   ->  figs/*.png, figs/*.pdf
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE.parent / "experiments" / "results"
FIGS = HERE / "figs"
FIGS.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.size": 9,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "figure.dpi": 200,
    "savefig.bbox": "tight",
})

FEATURE_EN = {
    "abs_z": "Strength of deviation, |z|",
    "text_dist": "Description distance to group",
    "log_ratio": "Log ratio to group median",
    "z": "Direction of deviation, z",
    "log_qty": "Log quantity",
    "log_group_size": "Group size",
    "group_spread": "Price spread in group",
    "unit_piece": "Piece-type unit",
    "src_contract": "Price from contract",
    "src_unit_value": "Price from item unit value",
    "unit_weight": "Weight unit (kg)",
    "pack_converted": "Price converted from pack size",
    "desc_generic": "Generic description",
    "has_pack": "Pack size in description",
    "unit_volume": "Volume unit (l)",
    "pack_mismatch": "Price resembles per-pack price",
    "is_extreme": "Extreme (3 IQR)",
    "is_noise": "Density outlier",
    "src_expected": "Price from expected value",
}


def save(fig, name: str) -> None:
    for ext in ("png", "pdf"):
        fig.savefig(FIGS / f"{name}.{ext}")
    plt.close(fig)
    print(f"  -> figs/{name}.png")


def legend(ax, loc: str = "best", *, fontsize: float = 7.0, ncol: int = 1) -> None:
    """Legend on an opaque white backing, so an unavoidable overlap stays readable."""
    ax.legend(loc=loc, fontsize=fontsize, ncol=ncol, frameon=True, framealpha=0.92, edgecolor="none",
              facecolor="white", borderpad=0.4, handlelength=1.6, labelspacing=0.35)


def fig_importance() -> None:
    """Global importance: mean |phi| over flagged items, in risk points."""
    t = pd.read_csv(RES / "importance.csv", encoding="utf-8-sig", index_col=0)["mean_abs_phi_points"]
    t.index = [FEATURE_EN.get(i.split(" — ")[0], i) for i in t.index]
    t = t[t >= 0.1].sort_values()
    fig, ax = plt.subplots(figsize=(4.6, 3.4))
    ax.barh(t.index, t.to_numpy(), color="#3b6ea5")
    ax.set_xscale("log")
    ax.set_xlabel("Mean |Shapley value|, risk points (log scale)")
    ax.grid(axis="y", visible=False)
    for y, v in enumerate(t.to_numpy()):
        ax.text(v * 1.08, y, f"{v:.1f}", va="center", fontsize=7)
    ax.set_xlim(0.08, t.max() * 3)
    save(fig, "fig_importance")


def fig_synthetic_recall() -> None:
    """Recall by injected error type for the main variants, both categories."""
    t = pd.read_csv(RES / "synthetic.csv", encoding="utf-8-sig")
    methods = {
        "перший етап v2": "Screening (v2)",
        "v2, калібратор на першій розмітці (з рішеннями v1)": "Calibrator, sighted labels",
        "v2, калібратор на сліпій розмітці, монотонний": "Calibrator, blind labels",
        "гібрид, калібратор на сліпій розмітці, монотонний": "Hybrid, blind labels",
    }
    types = [("recall moderate", "Moderate\n(×2–3)"), ("recall strong", "Strong\n(×5–10)"),
             ("recall unit", "Unit scale\n(×1000)"), ("recall lot_total", "Lot total\n(×qty)")]
    colors = ["#8c8c8c", "#d98c4a", "#3b6ea5", "#5aa469"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), sharey=True)
    for ax, (cat, title) in zip(axes, (("15", "CPV 15 (training category)"), ("03", "CPV 03 (held out)")),
                                strict=True):
        sub = t[t["категорія"].str.startswith(cat)].set_index("метод")
        x = np.arange(len(types))
        w = 0.2
        for k, (m, label) in enumerate(methods.items()):
            vals = [sub.loc[m, c] for c, _ in types]
            ax.bar(x + (k - 1.5) * w, vals, w, label=label, color=colors[k])
        ax.set_xticks(x, [lbl for _, lbl in types])
        ax.set_ylim(0, 1.15)
        ax.set_title(title, fontsize=9)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Recall")
    legend(axes[0], loc="upper left", fontsize=6.5, ncol=2)
    save(fig, "fig_synthetic_recall")


ANN = HERE.parent / "annotation"


def _labels(pattern: str) -> dict[int, tuple[str, str]]:
    import glob
    import json

    out = {}
    for f in sorted(glob.glob(str(ANN / pattern))):
        for k, v in json.load(open(f, encoding="utf8")).items():
            out[int(k)] = ("not_anomaly" if v[0] == "false_positive" else v[0], v[1])
    return out


def fig_ablation() -> None:
    """AP of the screening stage and its ablations under the three label variants."""
    rows = {
        "v1": "v1 (перший етап, як у v1) — власний поріг",
        "+ pack sizes": "+ перерахунок фасовки — власний поріг",
        "+ finer split\n(v2 screening)": "+ дрібніший текстовий поділ (перший етап v2) — власний поріг",
        "v2 screening\nw/o CPV\ngrouping": "перший етап v2 без групування за ДК 021 — власний поріг",
        "v2 screening\nw/o semantic\nsplit": "перший етап v2 без текстового поділу — власний поріг",
        "v2 + calibrator": "v2: перший етап + калібратор (вкладена CV)",
    }
    variants = [("sighted", "Sighted labels", "#8c8c8c"), ("blind", "Blind labels", "#3b6ea5"),
                ("adjusted", "Blind + human check", "#5aa469")]
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    x = np.arange(len(rows))
    w = 0.26
    for k, (kind, label, color) in enumerate(variants):
        t = pd.read_csv(RES / f"labels_{kind}.csv", encoding="utf-8-sig", index_col=0)
        vals = [t.loc[key, "ap"] for key in rows.values()]
        ax.bar(x + (k - 1) * w, vals, w, label=label, color=color)
    ax.set_xticks(x, list(rows), fontsize=7.5)
    ax.set_ylabel("Average precision (weighted)")
    ax.set_ylim(0, 1)
    ax.grid(axis="x", visible=False)
    legend(ax, loc="upper left", ncol=3)
    save(fig, "fig_ablation")


def fig_agreement() -> None:
    """Confusion matrices between annotation rounds."""
    import json

    sighted, blind = _labels("decisions*.json"), _labels("blind_decisions_*.json")
    human = {int(k): v for k, v in json.load(open(ANN / "human_labels.json", encoding="utf8")).items()}
    cls = ["confirmed", "not_anomaly", "needs_review"]
    names = ["confirmed", "not\nanomalous", "cannot\njudge"]

    def matrix(a: dict, b: dict) -> np.ndarray:
        m = np.zeros((3, 3), int)
        for i in set(a) & set(b):
            m[cls.index(a[i] if isinstance(a[i], str) else a[i][0]),
              cls.index(b[i] if isinstance(b[i], str) else b[i][0])] += 1
        return m

    pairs = [(matrix(sighted, blind), "Sighted (rows) vs blind (columns)", "n = 400, κ = 0.82 (binary)"),
             (matrix(human, blind), "Human (rows) vs blind LLM (columns)", "n = 80, κ = 0.64 (binary)")]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))
    fig.subplots_adjust(wspace=0.55)
    for ax, (m, title, note) in zip(axes, pairs, strict=True):
        ax.imshow(np.log1p(m), cmap="Blues")
        for (r, c), v in np.ndenumerate(m):
            ax.text(c, r, str(v), ha="center", va="center", fontsize=8,
                    color="white" if v > m.max() / 3 else "black")
        ax.set_xticks(range(3), names, fontsize=7)
        ax.set_yticks(range(3), names, fontsize=7)
        ax.set_title(f"{title}\n{note}", fontsize=8)
        ax.grid(False)
    save(fig, "fig_agreement")


def fig_label_composition() -> None:
    """Blind labels by stratum: share of each reason."""
    import json

    blind = _labels("blind_decisions_*.json")
    strata = {int(k): v for k, v in json.load(open(ANN / "strata.json", encoding="utf8"))["strata"].items()}
    reasons = [("overpriced", "over-priced", "#c0504d"), ("underpriced", "under-priced", "#4f81bd"),
               ("unit_error", "unit error", "#f0a04b"), ("data_error", "other data error", "#9b6fb0"),
               ("justified", "not anomalous", "#cfcfcf"), ("other", "cannot judge", "#7f7f7f")]
    order = [("top", "Top-50 flagged by v1"), ("mid", "Other flagged by v1"), ("normal", "Not flagged by v1")]
    fig, ax = plt.subplots(figsize=(3.5, 2.7))
    ticks = []
    for y, (s, label) in enumerate(order):
        items = [blind[i] for i in blind if strata.get(i) == s]
        left = 0.0
        for key, _, color in reasons:
            share = sum(1 for st, rs in items if rs == key) / len(items)
            ax.barh(y, share, left=left, color=color, edgecolor="white", linewidth=0.5)
            left += share
        ticks.append(f"{label}\n(n = {len(items)})")
    ax.set_yticks(range(3), ticks, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("Share of annotated items")
    ax.grid(axis="y", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in reasons]
    fig.subplots_adjust(bottom=0.36)
    fig.legend(handles, [n for _, n, _ in reasons], fontsize=6.5, ncol=3, loc="lower center",
               bbox_to_anchor=(0.55, 0.0), frameon=False, columnspacing=1.0, handlelength=1.2)
    save(fig, "fig_labels")


def fig_pr_curves() -> None:
    """Design-weighted precision–recall curves on blind labels."""
    path = RES / "scores_blind.csv"
    if not path.exists():
        print("  (scores_blind.csv missing: run exp_labels.py blind)")
        return
    t = pd.read_csv(path)
    y, w = t["y"].to_numpy(), t["weight"].to_numpy()
    curves = [("sigma3", "3σ, CPV class", "#8c8c8c", "--"), ("iforest_groups", "Isolation Forest in groups", "#d98c4a", "--"),
              ("v1", "v1 screening", "#b0b0b0", "-"), ("screening_v2", "v2 screening", "#5aa469", "-"),
              ("calibrator", "v2 + calibrator (nested CV)", "#3b6ea5", "-")]
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    for col, label, color, ls in curves:
        s = t[col].fillna(-1e9).to_numpy()
        order = np.argsort(-s, kind="stable")
        tp = np.cumsum(w[order] * y[order])
        fp = np.cumsum(w[order] * (1 - y[order]))
        prec, rec = tp / (tp + fp), tp / tp[-1]
        ax.plot(rec, prec, ls, color=color, label=label, linewidth=1.4)
    ax.set_xlabel("Recall (weighted)")
    ax.set_ylabel("Precision (weighted)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    legend(ax, loc="lower left", fontsize=6.5)
    save(fig, "fig_pr")


if __name__ == "__main__":
    fig_importance()
    fig_synthetic_recall()
    fig_ablation()
    fig_agreement()
    fig_label_composition()
    fig_pr_curves()
