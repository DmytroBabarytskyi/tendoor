"""Підготовка текстів описів: лематизація українських слів (pymorphy3)."""

import re
from functools import lru_cache

_WORD = re.compile(r"[a-zа-яіїєґ']+")


@lru_cache(maxsize=1)
def _morph():
    import pymorphy3  # імпорт ліниво: словники завантажуються ~1 с

    return pymorphy3.MorphAnalyzer(lang="uk")


@lru_cache(maxsize=200_000)
def lemma(word: str) -> str:
    if not re.search(r"[а-яіїєґ]", word):
        return word  # латиниця (марки, моделі) лишається як є
    return _morph().parse(word)[0].normal_form


def lemmatize(text: str) -> str:
    """Вхід — уже очищений опис (description_clean); вихід — леми, розділені пробілами."""
    return " ".join(lemma(w) for w in _WORD.findall(text.lower()) if len(w) > 1)
