from decimal import Decimal

import pytest

from tendoor.services.normalization import (
    clean_description,
    cpv_chain,
    cpv_digits,
    cpv_level,
    cpv_parent,
    matches_filter,
    normalize_tender,
)


@pytest.mark.parametrize(
    ("code", "digits", "level", "parent"),
    [
        ("15311100-4", "15311100", 5, "15311000"),
        ("15310000-4", "15310000", 3, "15300000"),
        ("15300000-1", "15300000", 2, "15000000"),
        ("15000000-8", "15000000", 1, None),
        ("03220000-9", "03220000", 3, "03200000"),
    ],
)
def test_cpv_hierarchy(code, digits, level, parent):
    assert cpv_digits(code) == digits
    assert cpv_level(digits) == level
    assert cpv_parent(digits) == parent


def test_cpv_invalid_codes_rejected():
    assert cpv_digits(None) is None
    assert cpv_digits("9999-1") is None
    assert cpv_digits("1234") is None


def test_cpv_chain_contains_all_ancestors():
    chain = cpv_chain("15311100", "Картопля")
    assert [c.code for c in chain] == ["15311100", "15311000", "15310000", "15300000", "15000000"]
    assert chain[0].description == "Картопля"
    assert all(c.description is None for c in chain[1:])


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("ДК 021:2015 15310000-4 Картопля та картопляні вироби", "картопля картопляні вироби"),
        ("  Картопля   (код ДК021:2015 - 03210000-6)  ", "картопля"),
        ("Kартопля свіжа", "картопля свіжа"),  # латинська K у кириличному слові
        ("лот № 2 - Ноутбук Lenovo", "ноутбук lenovo"),  # латиниця в латинському слові не змінюється
    ],
)
def test_clean_description(raw, clean):
    assert clean_description(raw) == clean


def test_reporting_explicit_unit_prices(load_fixture):
    nt = normalize_tender(load_fixture("reporting_unit_value"))
    assert nt.method_type == "reporting"
    assert len(nt.items) == 4
    beet = nt.items[0]
    assert (beet.unit_code, beet.quantity, beet.unit_price, beet.price_source) == (
        "KGM",
        Decimal("200.0"),
        Decimal("18.000000"),
        "unit_value",
    )
    assert beet.cpv_code == "03220000"
    assert {"03220000", "03200000", "03000000"} <= set(nt.cpvs)


def test_single_item_lots_use_active_contract_else_expected(load_fixture):
    nt = normalize_tender(load_fixture("lot_single_item_contract"))
    sources = [i.price_source for i in nt.items]
    assert sources == ["contract", "contract", "expected", "contract"]
    first = nt.items[0]
    contract = next(c for c in nt.contracts if c.prozorro_contract_id == first.prozorro_contract_id)
    assert contract.status == "active"
    assert first.unit_price == (contract.amount / first.quantity).quantize(Decimal("0.000001"))
    # у лоті з договором pending ціна рахується з очікуваної вартості лота
    assert nt.items[2].prozorro_contract_id is None


def test_multi_item_without_prices_has_no_unit_price(load_fixture):
    nt = normalize_tender(load_fixture("multi_item_no_prices"))
    assert len(nt.items) == 12
    assert all(i.unit_price is None and i.price_source is None for i in nt.items)


def test_date_published_uses_date_created(load_fixture):
    doc = load_fixture("reporting_unit_value")
    nt = normalize_tender(doc)
    assert nt.date_published.isoformat() == doc["dateCreated"]


def test_matches_filter(load_fixture):
    doc = load_fixture("reporting_unit_value")  # овочі 03220000, goods
    assert matches_filter(doc, [], [])
    assert matches_filter(doc, ["0322"], ["goods"])
    assert not matches_filter(doc, ["15"], [])
    assert not matches_filter(doc, [], ["services"])
