"""Індекс однорідності вибірки (A2.1): оцінка ДО навчання, наскільки коректно порівнювати ціни в ній.

H = 0.4 · C + 0.3 · U + 0.3 · S, де
  C — концентрація класів ДК 021 (1 − нормована ентропія Шеннона розподілу за 4-значними класами),
  U — частка найпоширенішої базової одиниці виміру,
  S — компактність цін: 1 для міжквартильного розмаху log-ціни ≤ 0.7 (≈ 2 рази), лінійно до 0 при ≥ 2.7.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

WEIGHTS = {"cpv": 0.4, "unit": 0.3, "spread": 0.3}
MIN_ITEMS = 50


@dataclass(slots=True)
class Homogeneity:
    index: float
    level: str  # good | warn | bad
    n_items: int
    cpv_concentration: float
    unit_purity: float
    price_compactness: float
    cpv_classes: int
    units: int
    message: str

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


def _concentration(counts: pd.Series) -> float:
    if len(counts) <= 1:
        return 1.0
    p = counts / counts.sum()
    entropy = -(p * np.log(p)).sum()
    return float(1 - entropy / np.log(len(counts)))


def homogeneity(df: pd.DataFrame, good: float = 0.7, warn: float = 0.4) -> Homogeneity:
    """df: колонки cpv_code, base_unit_code, unit_price_base (позиції з ціною)."""
    n = len(df)
    if n == 0:
        return Homogeneity(0.0, "bad", 0, 0.0, 0.0, 0.0, 0, 0, "За обраними умовами немає позицій з ціною.")

    cpv4 = df["cpv_code"].fillna("").str[:4]
    units = df["base_unit_code"].fillna("?")
    c = _concentration(cpv4.value_counts())
    unit_counts = units.value_counts()
    u = float(unit_counts.iloc[0] / n)

    main = df[units == unit_counts.index[0]]["unit_price_base"].astype(float)
    logp = np.log(main[main > 0])
    iqr = float(logp.quantile(0.75) - logp.quantile(0.25)) if len(logp) >= 4 else 0.0
    s = float(np.clip(1 - (iqr - 0.7) / 2.0, 0, 1))

    h = round(WEIGHTS["cpv"] * c + WEIGHTS["unit"] * u + WEIGHTS["spread"] * s, 3)
    level = "good" if h >= good else "warn" if h >= warn else "bad"
    if n < MIN_ITEMS:
        level = "bad" if level == "bad" else "warn"
        message = f"Замало позицій ({n}) для надійного виявлення — розширте період."
    elif level == "good":
        message = "Вибірка однорідна: ціни порівнянні, виявлення буде точним."
    else:
        message = (
            "Вибірка змішана. Чим менший розкид категорій, тим точніша детекція — "
            "звузьте коди ДК 021 або оберіть одну одиницю виміру."
        )
    return Homogeneity(
        h, level, n, round(c, 3), round(u, 3), round(s, 3), int(cpv4.nunique()), int(units.nunique()), message
    )
