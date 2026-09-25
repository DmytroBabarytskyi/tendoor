"""Розбір фасовки з опису позиції: «450 г», «5 л», «10×10 г», «1 кг» → кількість у кг або л.

Потрібен, бо в одиницях «штука», «пачка», «пляшка» порівнюються різні фасовки (олія 1 л і 5 л),
а для позицій у кг ціна за упаковку, записана як ціна за кілограм, дає хибну «аномалію» або навпаки.
"""

import re

import numpy as np
import pandas as pd

# одиниці, в яких ціна залежить від невідомого розміру упаковки
PIECE_UNITS = {"H87", "NMP", "PK", "BO", "JR", "CT", "BX"}
WEIGHT_VOLUME = {"KGM": "kg", "LTR": "l"}

_NUM = r"(\d+(?:[.,]\d+)?)"
_UNIT = r"(кг|кілограм\w*|г|гр|грам\w*|мл|л|літр\w*)"
_END = r"(?![а-яіїєґa-z])"
_MULTI = re.compile(rf"(\d+)\s*[xх×*]\s*{_NUM}\s*{_UNIT}{_END}")
_SINGLE = re.compile(rf"{_NUM}\s*{_UNIT}{_END}")
_SCALE = {
    "кг": ("kg", 1.0),
    "кілограм": ("kg", 1.0),
    "г": ("kg", 0.001),
    "гр": ("kg", 0.001),
    "грам": ("kg", 0.001),
    "мл": ("l", 0.001),
    "л": ("l", 1.0),
    "літр": ("l", 1.0),
}

MIN_SIZE, MAX_SIZE = 0.005, 60.0  # правдоподібна фасовка: від 5 г до 60 кг/л


def _scale(unit: str) -> tuple[str, float]:
    for key in sorted(_SCALE, key=len, reverse=True):
        if unit.startswith(key):
            return _SCALE[key]
    raise KeyError(unit)


def parse_pack(text: str | None) -> tuple[float, str] | None:
    """Розмір упаковки (кількість, 'kg' | 'l') або None. Перший знайдений розмір — основний."""
    if not text:
        return None
    t = text.lower().replace(" ", " ")
    m = _MULTI.search(t)
    if m:
        kind, k = _scale(m.group(3))
        size = int(m.group(1)) * float(m.group(2).replace(",", ".")) * k
    else:
        m = _SINGLE.search(t)
        if not m:
            return None
        kind, k = _scale(m.group(2))
        size = float(m.group(1).replace(",", ".")) * k
    return (size, kind) if MIN_SIZE <= size <= MAX_SIZE else None


def normalize_packs(d: pd.DataFrame) -> pd.DataFrame:
    """Для штучних одиниць з відомою фасовкою: ціна → грн/кг (грн/л), одиниця → KGM (LTR).
    Додає стовпці pack_size, pack_converted."""
    d = d.copy()
    packs = d["description_raw"].map(parse_pack)
    d["pack_size"] = packs.map(lambda p: p[0] if p else np.nan)
    kinds = packs.map(lambda p: p[1] if p else None)
    conv = d["base_unit_code"].isin(PIECE_UNITS) & d["pack_size"].notna()
    d["pack_converted"] = conv
    d.loc[conv, "price"] = d.loc[conv, "price"] / d.loc[conv, "pack_size"]
    d.loc[conv, "qty"] = d.loc[conv, "qty"] * d.loc[conv, "pack_size"]
    d.loc[conv, "base_unit_code"] = kinds[conv].map({"kg": "KGM", "l": "LTR"})
    return d
