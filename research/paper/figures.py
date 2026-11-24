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


if __name__ == "__main__":
    fig_importance()
    fig_synthetic_recall()
