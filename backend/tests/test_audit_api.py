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
