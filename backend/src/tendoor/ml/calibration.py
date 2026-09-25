"""Другий етап v2: калібрування ризику класифікатором, донавченим на вердиктах аудиторів.

Некерований етап (групи, DBSCAN, z) знаходить кандидатів, але не знає, які відхилення аудитор
вважає справжніми. Класифікатор градієнтного бустингу отримує ознаки першого етапу й повертає
ймовірність того, що аудитор підтвердить аномалію. Ознаки не залежать від конкретного товару,
тож модель, навчена на одній вибірці, переноситься на інші категорії.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MODEL_PATH = Path(__file__).parent / "models" / "calibrator_v2.joblib"

FEATURES = [
    "abs_z",
    "z",
    "log_ratio",
    "is_extreme",
    "is_noise",
    "log_group_size",
    "group_spread",
    "text_dist",
    "desc_generic",
    "pack_converted",
    "pack_mismatch",
    "has_pack",
    "unit_piece",
    "unit_weight",
    "unit_volume",
    "src_unit_value",
    "src_contract",
    "src_expected",
    "log_qty",
]

# узагальнені описи («продукти харчування різні», «згідно накладної») — позиція не порівнювана
_GENERIC = re.compile(r"продукт\w*\s+харчуван|різн[іи]|асортимент|згідно|накладн|продукці[яї]|\bдк\s*0?21")


def _text_distance(texts: pd.Series) -> np.ndarray:
    """Косинусна відстань опису позиції до «середнього» опису групи (TF-IDF): 0 — типовий опис."""
    try:
        m = TfidfVectorizer(min_df=1, sublinear_tf=True).fit_transform(texts)
    except ValueError:
        return np.zeros(len(texts))
    centroid = np.asarray(m.mean(axis=0))
    return 1 - cosine_similarity(m, centroid).ravel()


def add_features(items: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    """Ознаки для калібратора; d — підготовлені позиції з тими самими індексами, що й items."""
    out = items.copy()
    z = out["robust_z"].astype(float)
    out["z"] = z.fillna(0)
    out["abs_z"] = z.abs().fillna(0)
    out["log_ratio"] = np.log(out["ratio"].astype(float)).replace([np.inf, -np.inf], 0).fillna(0)
    sizes = out.groupby("group")["item_id"].transform("size")
    out["log_group_size"] = np.log(sizes.astype(float))
    out["group_spread"] = out["group_spread"].astype(float).fillna(0)
    out["text_dist"] = 0.0
    for _, idx in out[out["risk"].notna()].groupby("group").groups.items():
        out.loc[idx, "text_dist"] = _text_distance(d.loc[idx, "text"])
    desc = d["description_raw"].str.lower()
    out["desc_generic"] = desc.str.contains(_GENERIC).astype(float)
    out["pack_converted"] = out["pack_converted"].astype(float)
    out["has_pack"] = d["pack_size"].notna().astype(float)
    # ціна за упаковку, записана як ціна за кг/л: відношення до медіани ≈ розміру упаковки
    weightlike = (
        d["base_unit_code"].isin(["KGM", "LTR"]) & ~d["pack_converted"].astype(bool) & d["pack_size"].notna()
    )
    mismatch = (out["log_ratio"] - np.log(d["pack_size"].astype(float))).abs()
    out["pack_mismatch"] = np.where(weightlike, mismatch, 9.0)
    unit = d["unit_original"]
    out["unit_piece"] = unit.isin(["H87", "NMP", "PK", "BO", "JR", "SET", "KT", "E50"]).astype(float)
    out["unit_weight"] = (d["base_unit_code"] == "KGM").astype(float)
    out["unit_volume"] = (d["base_unit_code"] == "LTR").astype(float)
    for src in ("unit_value", "contract", "expected"):
        out[f"src_{src}"] = (d["price_source"] == src).astype(float)
    out["log_qty"] = d["log_qty"]
    out["is_extreme"] = out["is_extreme"].astype(float)
    out["is_noise"] = out["is_noise"].astype(float)
    return out


@dataclass
class Calibrator:
    model: HistGradientBoostingClassifier
    features: list[str] = field(default_factory=lambda: list(FEATURES))
    meta: dict = field(default_factory=dict)

    @classmethod
    def fit(
        cls, x: pd.DataFrame, y: np.ndarray, meta: dict | None = None, random_state: int = 42
    ) -> "Calibrator":
        model = HistGradientBoostingClassifier(
            max_depth=3,
            learning_rate=0.05,
            max_iter=300,
            l2_regularization=1.0,
            min_samples_leaf=10,
            class_weight="balanced",
            random_state=random_state,
        )
        model.fit(x[FEATURES].astype(float), y)
        return cls(model, list(FEATURES), meta or {})

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(x[self.features].astype(float))[:, 1]

    def save(self, path: Path = MODEL_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "features": self.features, "meta": self.meta}, path)


_cache: dict[str, Calibrator | None] = {}


def load_calibrator(path: Path = MODEL_PATH) -> Calibrator | None:
    key = str(path)
    if key not in _cache:
        if path.exists():
            obj = joblib.load(path)
            _cache[key] = Calibrator(obj["model"], obj["features"], obj["meta"])
        else:
            _cache[key] = None
    return _cache[key]
