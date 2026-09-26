"""A3: життєвий цикл перевірки позиції — машина станів із принципом «чотирьох очей».

    (немає) ──взяти в роботу──▶ в роботі ──надіслати──▶ на погодженні ──погодити──▶ погоджено
       │                            ▲                        │    ▲
       └────────надіслати одразу────┼────────────────────────┘    │ виправити й надіслати знову
                                    └──────── повернуто ◀─повернути (з коментарем)

Переходи виконує автор висновку (аудитор, що взяв позицію) або інший аудитор-погоджувач. Функція
transition чиста: отримує поточний стан і дію, повертає зміни або ReviewError — тож правила перевіряються
модульними тестами без БД, а репозиторій лише застосовує зміни атомарно (рядок блокується FOR UPDATE).
"""

from dataclasses import dataclass
from typing import Literal

Action = Literal["take", "submit", "approve", "return"]
REVIEWER_ROLES = ("admin", "auditor")

LABELS = {
    "in_progress": "в роботі",
    "submitted": "на погодженні",
    "returned": "повернуто",
    "approved": "погоджено",
}


class ReviewError(ValueError):
    def __init__(self, message: str, conflict: bool = False) -> None:
        super().__init__(message)
        self.conflict = conflict  # 409 — стан змінив інший користувач; інакше 403/422


@dataclass(frozen=True, slots=True)
class Current:
    state: str
    author_id: int | None


def transition(current: Current | None, action: Action, actor_id: int, payload: dict | None = None) -> dict:
    """Зміни полів перевірки для дії actor_id або ReviewError, якщо перехід заборонено."""
    payload = payload or {}
    mine = current is not None and current.author_id == actor_id

    if action == "take":
        if current is None:
            return {"state": "in_progress", "user_id": actor_id}
        if current.state == "approved":
            raise ReviewError("Перевірку вже погоджено", conflict=True)
        if not mine:
            raise ReviewError(f"Позиція {LABELS[current.state]} в іншого аудитора", conflict=True)
        raise ReviewError("Позиція вже у вас у роботі", conflict=True)

    if action == "submit":
        _validate_conclusion(payload)
        fields = {
            "state": "submitted",
            "status": payload["status"],
            "reason": payload["reason"],
            "comment": payload.get("comment"),
            "reviewer_id": None,
            "reviewed_at": None,
            "review_comment": None,
        }
        if current is None:
            return {**fields, "user_id": actor_id}  # висновок одразу, без окремого «взяти в роботу»
        if current.state == "approved":
            raise ReviewError("Погоджену перевірку змінити не можна", conflict=True)
        if not mine:
            raise ReviewError(
                "Надіслати висновок може лише аудитор, який узяв позицію в роботу", conflict=True
            )
        return fields

    if action in ("approve", "return"):
        if current is None or current.state != "submitted":
            raise ReviewError("Погоджувати можна лише висновок, надісланий на погодження", conflict=True)
        if mine:
            raise ReviewError("Автор не може погоджувати власний висновок (принцип «чотирьох очей»)")
        comment = (payload.get("comment") or "").strip() or None
        if action == "return" and not comment:
            raise ReviewError("Поверніть висновок з коментарем: що саме потрібно доопрацювати")
        return {
            "state": "approved" if action == "approve" else "returned",
            "reviewer_id": actor_id,
            "reviewed_at": "now",
            "review_comment": comment,
        }

    raise ReviewError(f"Невідома дія: {action}")


def _validate_conclusion(payload: dict) -> None:
    if not payload.get("status") or not payload.get("reason"):
        raise ReviewError("Оберіть висновок і причину")
    if payload["status"] == "confirmed" and payload["reason"] == "justified":
        raise ReviewError("Підтверджена аномалія не може бути обґрунтованою")
