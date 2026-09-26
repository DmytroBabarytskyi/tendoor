"""Машина станів перевірки позиції (A3): переходи, принцип «чотирьох очей», повні висновки."""

import pytest

from tendoor.services.review import Current, ReviewError, transition

A, B = 1, 2  # автор висновку і другий аудитор
OK = {"status": "confirmed", "reason": "overpriced", "comment": "ціна вп'ятеро вища"}


def test_take_new_item():
    assert transition(None, "take", A) == {"state": "in_progress", "user_id": A}


@pytest.mark.parametrize(
    ("current", "message"),
    [
        (Current("in_progress", B), "в іншого"),
        (Current("submitted", B), "в іншого"),
        (Current("in_progress", A), "вже у вас"),
        (Current("approved", B), "погоджено"),
    ],
)
def test_take_conflicts(current, message):
    with pytest.raises(ReviewError, match=message) as e:
        transition(current, "take", A)
    assert e.value.conflict


def test_submit_directly_and_after_taking():
    direct = transition(None, "submit", A, OK)
    assert direct["state"] == "submitted" and direct["user_id"] == A and direct["status"] == "confirmed"
    after = transition(Current("in_progress", A), "submit", A, OK)
    assert after["state"] == "submitted" and "user_id" not in after
    fixed = transition(Current("returned", A), "submit", A, OK)
    assert fixed["state"] == "submitted" and fixed["review_comment"] is None and fixed["reviewer_id"] is None


@pytest.mark.parametrize(
    ("current", "payload", "message"),
    [
        (Current("in_progress", B), OK, "лише аудитор"),
        (Current("approved", A), OK, "Погоджену"),
        (None, {"status": "confirmed"}, "причину"),
        (None, {"status": "confirmed", "reason": "justified"}, "обґрунтованою"),
    ],
)
def test_submit_rules(current, payload, message):
    with pytest.raises(ReviewError, match=message):
        transition(current, "submit", A, payload)


def test_four_eyes():
    with pytest.raises(ReviewError, match="чотирьох очей") as e:
        transition(Current("submitted", A), "approve", A)
    assert not e.value.conflict
    approved = transition(Current("submitted", A), "approve", B)
    assert approved == {"state": "approved", "reviewer_id": B, "reviewed_at": "now", "review_comment": None}


def test_return_requires_comment_and_only_submitted_can_be_reviewed():
    with pytest.raises(ReviewError, match="коментарем"):
        transition(Current("submitted", A), "return", B, {"comment": "  "})
    back = transition(Current("submitted", A), "return", B, {"comment": "перевірте договір"})
    assert back["state"] == "returned" and back["review_comment"] == "перевірте договір"
    for state in ("in_progress", "returned", "approved"):
        with pytest.raises(ReviewError, match="надісланий на погодження"):
            transition(Current(state, A), "approve", B)
    with pytest.raises(ReviewError):
        transition(None, "approve", B)
