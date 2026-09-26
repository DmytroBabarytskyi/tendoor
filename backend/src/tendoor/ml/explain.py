"""Локальні пояснення рішення калібратора: внесок кожної ознаки в ризик конкретної позиції (значення Шеплі).

Значення Шеплі ознаки j для позиції x — її середній граничний внесок у прогноз по всіх порядках
«додавання» ознак до коаліції:

    φ_j(x) = Σ_{S ⊆ F∖{j}} |S|! (d − |S| − 1)! / d! · [f(x_{S∪{j}}) − f(x_S)],

де f(x_S) — прогноз, коли ознаки з S взято з x, а решта — з фонових (звичайних) позицій. Сума внесків
дорівнює різниці між прогнозом для x і середнім прогнозом для фону (властивість ефективності).
Точний розрахунок потребує 2^d коаліцій (d = 19), тому використано оцінку Монте-Карло за випадковими
перестановками (Štrumbelj, Kononenko, 2014): для перестановки π ознаки по черзі переносяться з x у фонову
точку, приріст прогнозу на кожному кроці — внесок відповідної ознаки.
"""

import warnings

import numpy as np
import pandas as pd

from tendoor.ml.calibration import Calibrator

# назви ознак для аудитора (пояснення в інтерфейсі та звіті)
FEATURE_LABELS = {
    "abs_z": "Сила відхилення від медіани групи",
    "z": "Напрям відхилення (дорожче чи дешевше)",
    "log_ratio": "Відношення ціни до медіани",
    "is_extreme": "Екстремальне значення ціни",
    "is_noise": "Нетипове поєднання ціни, обсягу й дати",
    "log_group_size": "Розмір групи порівнюваних товарів",
    "group_spread": "Розкид цін у групі",
    "text_dist": "Відмінність опису від решти групи",
    "desc_generic": "Узагальнений опис («продукти різні» тощо)",
    "pack_converted": "Ціну перераховано з фасовки",
    "pack_mismatch": "Схожість на ціну за упаковку",
    "has_pack": "Фасовка вказана в описі",
    "unit_piece": "Штучна одиниця виміру",
    "unit_weight": "Вагова одиниця (кг)",
    "unit_volume": "Об'ємна одиниця (л)",
    "src_unit_value": "Ціна вказана за одиницю",
    "src_contract": "Ціну взято з договору",
    "src_expected": "Ціну взято з очікуваної вартості",
    "log_qty": "Обсяг закупівлі",
}


def shapley_values(
    cal: Calibrator,
    x: pd.DataFrame,
    background: pd.DataFrame,
    n_permutations: int = 24,
    random_state: int = 42,
) -> tuple[np.ndarray, float]:
    """(φ — масив n × d у одиницях імовірності, базове значення E[f(фон)])."""
    rng = np.random.default_rng(random_state)
    xs = x[cal.features].to_numpy(dtype=float)
    bg = background[cal.features].to_numpy(dtype=float)
    n, d = xs.shape
    phi = np.zeros((n, d))
    model = cal.model

    def predict(a: np.ndarray) -> np.ndarray:
        # модель навчена на DataFrame; масив без назв колонок дає лише попередження sklearn
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            return model.predict_proba(a)

    for _ in range(n_permutations):
        order = rng.permutation(d)
        z = bg[rng.integers(0, len(bg), size=n)].copy()  # для кожної позиції — своя фонова точка
        prev = predict(z)[:, 1]
        for j in order:
            z[:, j] = xs[:, j]
            cur = predict(z)[:, 1]
            phi[:, j] += cur - prev
            prev = cur
    phi /= n_permutations
    base = float(predict(bg)[:, 1].mean())
    return phi, base


def top_contributions(
    phi: np.ndarray, values: np.ndarray, features: list[str], k: int = 8
) -> list[list[dict]]:
    """Для кожної позиції — k найбільших за модулем внесків у пунктах ризику (0–100) зі значенням ознаки."""
    out = []
    for row, vals in zip(phi, values, strict=True):
        idx = np.argsort(-np.abs(row))[:k]
        out.append(
            [
                {
                    "feature": features[i],
                    "label": FEATURE_LABELS.get(features[i], features[i]),
                    "value": round(float(vals[i]), 4),
                    "points": round(float(100 * row[i]), 2),
                }
                for i in idx
                if abs(row[i]) >= 0.005  # менше за пів пункту ризику — не показуємо
            ]
        )
    return out
