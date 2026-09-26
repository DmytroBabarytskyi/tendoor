"""Конвеєр v1 виявлення аномальних цінових пропозицій.

1. Ієрархічне формування однорідних груп (агрегування знизу вгору):
   базова одиниця виміру + код ДК 021 (8 цифр); групи, менші за min_group_size, піднімаються
   на рівень категорії (5 цифр), далі класу (4 цифри). Великі групи дорозбиваються семантично:
   лематизація → TF-IDF → (TruncatedSVD) → K-Means, k — за коефіцієнтом силуету.
2. У кожній групі:
   а) правило екстремумів: log-ціна поза Q1 − k·IQR … Q3 + k·IQR (не спотворює подальше навчання);
   б) простір показників [w·log ціни, log обсягу, sin/cos місяця] → стандартизація → PCA;
   в) DBSCAN з автоматичним eps (точка «ліктя» графіка k-відстаней);
   г) модифіковане z-значення log-ціни (медіана та MAD, Iglewicz & Hoaglin).
3. Аномалія = екстремум АБО |z| ≥ z_strong АБО (шум DBSCAN І |z| ≥ min_price_z):
   щільнісний викид має бути саме ціновим, а не лише за обсягом чи датою.
4. Ризик-бал 0–100 = 100 · (1 − exp(−|z| / risk_scale)); пояснення — відношення до медіани групи.
"""

import time
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler, normalize

from tendoor.ml.calibration import add_features, load_calibrator
from tendoor.ml.explain import FEATURE_LABELS, shapley_values, top_contributions
from tendoor.ml.packaging import normalize_packs
from tendoor.ml.text import lemmatize

PIPELINE_VERSION = "v2.1"  # v2.1: пояснення рішень (значення Шеплі)
MAD_TO_SIGMA = 1.4826  # MAD → стандартне відхилення для нормального розподілу
CPV_LEVELS = (8, 5, 4)  # код, категорія, клас ДК 021

# слова, що не розрізняють товари: одиниці, пакування, загальні назви закупівлі
STOP_WORDS = [
    "кг",
    "г",
    "гр",
    "л",
    "мл",
    "шт",
    "уп",
    "упаковка",
    "пачка",
    "тонна",
    "кілограм",
    "штука",
    "літр",
    "продукт",
    "продукти",
    "харчування",
    "товар",
    "закупівля",
    "придбання",
    "постачання",
    "поставка",
    "потреба",
    "учень",
    "заклад",
    "ззсо",
    "здо",
    "їдальня",
    "дсту",
    "ту",
    "гост",
    "сорт",
    "клас",
    "вид",
]


@dataclass(slots=True)
class DetectionParams:
    min_group_size: int = 10
    cpv_grouping: bool = True
    text_split: bool = True
    text_split_min: int = 30  # групи, більші за це, дорозбиваються за текстом (v2: 30 замість 60)
    k_max: int = 8
    silhouette_min: float = 0.15  # нижче — текстовий поділ вважається неінформативним
    dbscan_min_samples: int = 5
    price_weight: float = 2.0
    extreme_iqr_factor: float = 3.0
    # значення підібрано перебором на реальних даних (синтетичні аномалії, F1 та average precision)
    z_strong: float = 4.0
    min_price_z: float = 3.0
    risk_scale: float = 3.0
    mad_floor: float = 0.15  # мінімальний розкид log-ціни (≈15 %): звичайні коливання ринку — не аномалія
    pca_variance: float = 0.9
    random_state: int = 42
    # v2
    pack_normalize: bool = True  # «штука/пачка/пляшка» з фасовкою в описі → грн/кг, грн/л
    text_subgroup_min: int = 5  # мінімальна підгрупа текстового поділу (v2)
    calibrate: bool = True  # ризик і рішення — від класифікатора, донавченого на вердиктах
    anomaly_threshold: float | None = None  # None — поріг, підібраний крос-валідацією разом із калібратором

    @classmethod
    def from_dict(cls, d: dict) -> "DetectionParams":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class GroupResult:
    label: int
    unit: str
    cpv_code: str | None  # рівень ієрархії, на якому сформовано групу (8, 5 або 4 цифри)
    top_terms: list[str]
    size: int
    median_price: float | None
    analysed: bool
    n_anomalies: int = 0
    eps: float | None = None
    explained_variance: float | None = None
    silhouette: float | None = None


@dataclass(slots=True)
class DetectionResult:
    items: (
        pd.DataFrame
    )  # item_id, group, is_anomaly, is_extreme, is_noise, robust_z, ratio, risk, pc1, pc2, price
    groups: list[GroupResult]
    metrics: dict


# ---------------------------------------------------------------- підготовка


def prepare(df: pd.DataFrame, p: DetectionParams | None = None) -> pd.DataFrame:
    """Вхід: item_id, description (необов'язково), description_clean, cpv_code, base_unit_code,
    unit_price_base, quantity_base, price_source (необов'язково), date_published.
    Лишаються позиції з додатними ціною та обсягом."""
    p = p or DetectionParams()
    d = df.copy()
    d["price"] = pd.to_numeric(d["unit_price_base"], errors="coerce").astype(float)
    d["qty"] = pd.to_numeric(d["quantity_base"], errors="coerce").astype(float)
    d = d[(d["price"] > 0) & (d["qty"] > 0)].copy()
    raw = d["description"] if "description" in d else d["description_clean"]
    d["description_raw"] = raw.fillna("").astype(str)
    d["price_source"] = d["price_source"].fillna("unknown") if "price_source" in d else "unknown"
    d["unit_original"] = d["base_unit_code"]
    if p.pack_normalize:
        d = normalize_packs(d)
    else:
        d["pack_size"], d["pack_converted"] = np.nan, False
    d["log_price"] = np.log(d["price"])
    d["log_qty"] = np.log(d["qty"])
    month = pd.to_datetime(d["date_published"], utc=True).dt.month
    d["month_sin"] = np.sin(2 * np.pi * month / 12)  # циклічне кодування: грудень поруч із січнем
    d["month_cos"] = np.cos(2 * np.pi * month / 12)
    d["cpv_code"] = d["cpv_code"].fillna("00000000")
    d["text"] = d["description_clean"].fillna("").map(lemmatize)
    return d.reset_index(drop=True)


# ---------------------------------------------------------------- формування груп


def _top_terms(tfidf, vocab: np.ndarray, mask: np.ndarray, n: int = 5) -> list[str]:
    weights = np.asarray(tfidf[mask].mean(axis=0)).ravel()
    return [vocab[i] for i in weights.argsort()[::-1][:n] if weights[i] > 0]


def split_by_text(texts: pd.Series, p: DetectionParams) -> tuple[np.ndarray, list[list[str]], float | None]:
    """Семантичний поділ групи: мітки, ключові терміни підгруп, силует (None — поділу немає)."""
    n = len(texts)
    try:
        vec = TfidfVectorizer(
            ngram_range=(1, 2), min_df=2, max_df=0.95, sublinear_tf=True, stop_words=STOP_WORDS
        )
        tfidf = vec.fit_transform(texts)
    except ValueError:  # порожній словник: однакові або порожні описи
        return np.zeros(n, dtype=int), [[]], None
    vocab = vec.get_feature_names_out()
    whole = [_top_terms(tfidf, vocab, np.ones(n, bool))]
    k_max = min(p.k_max, n // p.text_subgroup_min)
    if not p.text_split or n < p.text_split_min or k_max < 2 or tfidf.shape[1] < 3:
        return np.zeros(n, dtype=int), whole, None

    x = tfidf
    if tfidf.shape[1] > 60:
        x = TruncatedSVD(n_components=min(50, tfidf.shape[1] - 1), random_state=p.random_state).fit_transform(
            tfidf
        )
        x = normalize(x)  # косинусна близькість → евклідова відстань для K-Means

    rng = np.random.default_rng(p.random_state)
    sample = rng.choice(n, size=min(n, 3000), replace=False)
    best = None
    for k in range(2, k_max + 1):
        labels = KMeans(n_clusters=k, n_init=3, random_state=p.random_state).fit_predict(x)
        if np.bincount(labels, minlength=k).min() < p.text_subgroup_min or len(set(labels[sample])) < 2:
            continue  # у кожній підгрупі має бути достатньо позицій для статистики цін
        score = silhouette_score(x[sample], labels[sample])
        if best is None or score > best[1]:
            best = (labels, score)
    if best is None or best[1] < p.silhouette_min:
        return np.zeros(n, dtype=int), whole, None
    labels, score = best
    return labels, [_top_terms(tfidf, vocab, labels == g) for g in range(labels.max() + 1)], float(score)


def assign_groups(d: pd.DataFrame, p: DetectionParams) -> tuple[pd.Series, list[GroupResult]]:
    """Ієрархічне агрегування: код ДК 021 → категорія → клас; залишок — неаналізовані позиції."""
    group = pd.Series(-1, index=d.index)
    groups: list[GroupResult] = []

    def add(idx: pd.Index, unit: str, cpv: str | None, analysed: bool) -> None:
        sub = d.loc[idx]
        labels, terms, sil = (
            split_by_text(sub["text"], p) if analysed else (np.zeros(len(sub), int), [[]], None)
        )
        for sub_label in range(len(terms)):
            mask = labels == sub_label
            label = len(groups)
            group.loc[sub.index[mask]] = label
            groups.append(
                GroupResult(
                    label,
                    unit,
                    cpv,
                    terms[sub_label],
                    int(mask.sum()),
                    float(sub.loc[mask, "price"].median()),
                    analysed,
                    silhouette=sil,
                )
            )

    for unit, du in d.groupby("base_unit_code", sort=True):
        pending = du.index
        levels = CPV_LEVELS if p.cpv_grouping else (0,)
        for level in levels:
            key = du.loc[pending, "cpv_code"].str[:level] if level else pd.Series("", index=pending)
            sizes = key.map(key.value_counts())
            big = sizes >= p.min_group_size
            for code, idx in key[big].groupby(key[big]).groups.items():
                add(idx, unit, code.ljust(8, "0") if level else None, analysed=True)
            pending = pending[~big.to_numpy()]
            if len(pending) == 0:
                break
        if len(pending):
            add(pending, unit, None, analysed=False)
    return group, groups


# ---------------------------------------------------------------- аномалії в групі


def knee_eps(x: np.ndarray, k: int) -> float:
    """eps DBSCAN — «лікоть» відсортованих відстаней до k-го сусіда (максимум відхилення від хорди)."""
    k = min(k, len(x) - 1)
    dist = np.sort(NearestNeighbors(n_neighbors=k + 1).fit(x).kneighbors(x)[0][:, -1])
    if dist[-1] - dist[0] < 1e-9:
        return float(dist[-1]) or 0.5
    idx = np.arange(len(dist))
    chord = dist[0] + (dist[-1] - dist[0]) * idx / (len(dist) - 1)
    return float(max(dist[int(np.argmax(chord - dist))], 1e-3))


def analyse_group(g: pd.DataFrame, p: DetectionParams) -> tuple[pd.DataFrame, dict]:
    lp = g["log_price"]
    q1, q3 = lp.quantile(0.25), lp.quantile(0.75)
    iqr = q3 - q1
    extreme = (lp < q1 - p.extreme_iqr_factor * iqr) | (lp > q3 + p.extreme_iqr_factor * iqr)

    base = g[~extreme]
    med = float(base["log_price"].median())
    mad = float((base["log_price"] - med).abs().median()) * MAD_TO_SIGMA
    z = (lp - med) / max(mad, p.mad_floor)

    out = pd.DataFrame(index=g.index)
    out["is_extreme"] = extreme
    out["is_noise"] = False
    out["pc1"] = np.nan
    out["pc2"] = np.nan
    info: dict = {"eps": None, "explained_variance": None}

    cols = [c for c in ("log_price", "log_qty", "month_sin", "month_cos") if base[c].std() > 1e-9]
    if len(base) > p.dbscan_min_samples and len(cols) >= 2 and "log_price" in cols:
        scaler = StandardScaler().fit(base[cols])
        weights = np.array([p.price_weight if c == "log_price" else 1.0 for c in cols])
        xs = scaler.transform(g[cols]) * weights
        fit_mask = ~extreme.to_numpy()
        pca = PCA(n_components=p.pca_variance, svd_solver="full").fit(xs[fit_mask])
        if pca.n_components_ < 2:
            pca = PCA(n_components=2).fit(xs[fit_mask])
        xp = pca.transform(xs)
        eps = knee_eps(xp[fit_mask], p.dbscan_min_samples)
        labels = DBSCAN(eps=eps, min_samples=p.dbscan_min_samples).fit_predict(xp[fit_mask])
        out.loc[base.index, "is_noise"] = labels == -1
        out["pc1"], out["pc2"] = xp[:, 0], xp[:, 1]
        info = {
            "eps": round(eps, 4),
            "explained_variance": round(float(pca.explained_variance_ratio_.sum()), 4),
        }

    az = z.abs()
    out["robust_z"] = z
    out["ratio"] = np.exp(lp - med)
    out["is_anomaly"] = out["is_extreme"] | (az >= p.z_strong) | (out["is_noise"] & (az >= p.min_price_z))
    out["risk"] = 100 * (1 - np.exp(-az / p.risk_scale))
    out["group_spread"] = mad
    info["median_price"] = float(np.exp(med))
    return out, info


# ---------------------------------------------------------------- пояснення рішень

EXPLAIN_MIN_SHARE = 0.5  # пояснюються позиції з імовірністю ≥ половини порогу: аномалії й близькі до них


def _explain(items: pd.DataFrame, mask: pd.Series, prob: np.ndarray, threshold: float, cal, p) -> list[dict]:
    """Внески ознак (значення Шеплі) для підозрілих позицій; повертає глобальну важливість — середній |φ|."""
    analysed = items.loc[mask]
    candidates = analysed[prob >= threshold * EXPLAIN_MIN_SHARE]
    normal = analysed[prob < threshold * EXPLAIN_MIN_SHARE]
    if candidates.empty or len(normal) < 10:
        return []
    background = normal.sample(min(100, len(normal)), random_state=p.random_state)
    phi, _ = shapley_values(cal, candidates, background, random_state=p.random_state)
    values = candidates[cal.features].to_numpy(dtype=float)
    contributions = top_contributions(phi, values, cal.features)
    items.loc[candidates.index, "contributions"] = pd.Series(
        contributions, index=candidates.index, dtype=object
    )
    mean_abs = np.abs(phi).mean(axis=0) * 100
    order = np.argsort(-mean_abs)
    return [
        {
            "feature": cal.features[i],
            "label": FEATURE_LABELS.get(cal.features[i], cal.features[i]),
            "points": round(float(mean_abs[i]), 2),
        }
        for i in order
    ]


# ---------------------------------------------------------------- основна функція


def run_detection(df: pd.DataFrame, p: DetectionParams | None = None) -> DetectionResult:
    p = p or DetectionParams()
    started = time.perf_counter()
    d = prepare(df, p)
    group, groups = assign_groups(d, p)

    items = pd.DataFrame(
        {
            "item_id": d["item_id"],
            "group": group,
            "price": d["price"],
            "unit": d["base_unit_code"],
            "pack_size": d["pack_size"],
            "pack_converted": d["pack_converted"].astype(bool),
        }
    )
    for col, default in (("is_anomaly", False), ("is_extreme", False), ("is_noise", False)):
        items[col] = default
    for col in ("robust_z", "ratio", "risk", "pc1", "pc2", "group_spread"):
        items[col] = np.nan

    for gr in groups:
        if not gr.analysed or gr.size < p.min_group_size:
            gr.analysed = False
            continue
        idx = items.index[items["group"] == gr.label]
        res, info = analyse_group(d.loc[idx], p)
        items.loc[idx, res.columns] = res
        gr.n_anomalies = int(res["is_anomaly"].sum())
        gr.eps, gr.explained_variance = info["eps"], info["explained_variance"]
        gr.median_price = info["median_price"]

    for col in ("is_anomaly", "is_extreme", "is_noise"):
        items[col] = items[col].astype(bool)
    items["rule_anomaly"] = items["is_anomaly"]  # рішення першого (некерованого) етапу
    items = add_features(items, d)

    items["contributions"] = None
    importance: list[dict] = []
    calibrator = load_calibrator() if p.calibrate else None
    if calibrator is not None:
        # другий етап: ризик — імовірність підтвердження аудитором (модель донавчена на вердиктах)
        mask = items["risk"].notna()
        if mask.any():
            prob = calibrator.predict_proba(items.loc[mask])
            items.loc[mask, "risk"] = 100 * prob
            threshold = p.anomaly_threshold or calibrator.meta.get("threshold", 0.5)
            items.loc[mask, "is_anomaly"] = prob >= threshold
            importance = _explain(items, mask, prob, threshold, calibrator, p)
        counts = items[items["is_anomaly"]].groupby("group").size()
        for gr in groups:
            gr.n_anomalies = int(counts.get(gr.label, 0))
    analysed = int(items["risk"].notna().sum())
    n_anom = int(items["is_anomaly"].sum())
    sils = [g.silhouette for g in groups if g.silhouette is not None]
    metrics = {
        "pipeline_version": PIPELINE_VERSION,
        "n_input": len(df),
        "n_items": len(d),
        "n_analysed": analysed,
        "n_anomalies": n_anom,
        "n_extreme": int(items["is_extreme"].sum()),
        "anomaly_share": round(n_anom / analysed, 4) if analysed else 0.0,
        "n_groups": sum(1 for g in groups if g.analysed),
        "n_text_splits": len(set(sils)),
        "mean_silhouette": round(float(np.mean(sils)), 4) if sils else None,
        "n_pack_converted": int(items["pack_converted"].sum()),
        "calibrator": calibrator.meta.get("version") if calibrator is not None else None,
        "importance": importance,
        "seconds": round(time.perf_counter() - started, 2),
    }
    return DetectionResult(items=items, groups=groups, metrics=metrics)
