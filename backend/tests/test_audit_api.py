import pytest

VERDICT = {"status": "confirmed", "reason": "overpriced", "comment": "ціна у 5 разів вища за ринкову"}


@pytest.mark.parametrize(("role", "code"), [("auditor", 200), ("admin", 200), ("analyst", 403)])
async def test_verdict_roles(client, login, role, code):
    headers = await login(f"{role}@test.ua")
    assert (await client.put("/api/items/1/verdict", json=VERDICT, headers=headers)).status_code == code


@pytest.mark.parametrize(
    "body",
    [
        {**VERDICT, "status": "maybe"},
        {**VERDICT, "reason": "cheap"},
        {**VERDICT, "status": "confirmed", "reason": "justified"},  # суперечливий вердикт
        {**VERDICT, "comment": "x" * 2001},
    ],
)
async def test_verdict_validation(client, login, body):
    headers = await login("auditor@test.ua")
    assert (await client.put("/api/items/1/verdict", json=body, headers=headers)).status_code == 422


async def test_verdict_for_unknown_item_404(client, login):
    headers = await login("auditor@test.ua")
    assert (await client.put("/api/items/999/verdict", json=VERDICT, headers=headers)).status_code == 404


async def test_verdict_saved_and_listed(client, login, fake):
    headers = await login("auditor@test.ua")
    await client.put("/api/items/1/verdict", json=VERDICT, headers=headers)
    assert fake.verdicts.items[1]["user_id"] == fake.auditor.id
    page = (await client.get("/api/verdicts?mine=true", headers=headers)).json()
    assert page["total"] == 1 and page["items"][0]["reason"] == "overpriced"
    card = (await client.get("/api/items/1", headers=headers)).json()
    assert card["verdict"]["status"] == "confirmed"


async def test_review_cycle_between_two_auditors(client, login, fake):
    author = await login("auditor@test.ua")
    reviewer = await login("auditor2@test.ua")
    assert (await client.post("/api/items/1/take", headers=author)).json()["state"] == "in_progress"
    # позиція в роботі в іншого — друга людина не може її взяти
    assert (await client.post("/api/items/1/take", headers=reviewer)).status_code == 409
    assert (await client.put("/api/items/1/verdict", json=VERDICT, headers=author)).json()[
        "state"
    ] == "submitted"
    # автор не погоджує власний висновок
    own = await client.post("/api/items/1/review", json={"decision": "approve"}, headers=author)
    assert own.status_code == 403
    queue = (await client.get("/api/verdicts?queue=review", headers=reviewer)).json()
    assert queue["total"] == 1
    assert (await client.get("/api/badges", headers=reviewer)).json()["to_review"] == 1
    back = await client.post("/api/items/1/review", json={"decision": "return"}, headers=reviewer)
    assert back.status_code == 422  # повернути можна лише з коментарем
    back = await client.post(
        "/api/items/1/review", json={"decision": "return", "comment": "додайте договір"}, headers=reviewer
    )
    assert back.json()["state"] == "returned"
    assert (await client.get("/api/badges", headers=author)).json()["returned"] == 1
    await client.put("/api/items/1/verdict", json=VERDICT, headers=author)
    done = await client.post("/api/items/1/review", json={"decision": "approve"}, headers=reviewer)
    assert done.json()["state"] == "approved" and fake.verdicts.items[1]["reviewer_id"] == fake.auditor2.id
    assert (await client.put("/api/items/1/verdict", json=VERDICT, headers=author)).status_code == 409


async def test_analyst_cannot_review(client, login):
    headers = await login("analyst@test.ua")
    resp = await client.post("/api/items/1/review", json={"decision": "approve"}, headers=headers)
    assert resp.status_code == 403
