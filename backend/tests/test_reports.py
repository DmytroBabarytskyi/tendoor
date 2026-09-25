from datetime import UTC, date, datetime
from io import BytesIO

from openpyxl import load_workbook

from tendoor.services.reports import build_xlsx


def test_xlsx_report_structure():
    request = {
        "id": 5,
        "cpv_prefixes": ["1531"],
        "unit_codes": [],
        "date_from": date(2026, 9, 1),
        "date_to": date(2026, 9, 30),
        "homogeneity_details": {"index": 0.91},
    }
    run = {
        "pipeline_version": "v1",
        "metrics": {"n_analysed": 100, "n_groups": 4, "n_anomalies": 1, "anomaly_share": 0.01},
    }
    anomaly = {
        "risk_score": 97.5,
        "unit_price_base": 180.0,
        "base_unit_code": "KGM",
        "median_price": 18.0,
        "price_ratio": 10.0,
        "description": "Картопля",
        "cpv_code": "03212100",
        "entity_name": "Школа",
        "entity_edrpou": "123",
        "entity_region": "Київ",
        "tender_code": "UA-2026-09-01-000001-a",
        "date_published": datetime(2026, 9, 1, tzinfo=UTC),
        "verdict_status": "confirmed",
        "verdict_reason": "overpriced",
    }
    cats = [
        {
            "cpv_code": "03212100",
            "base_unit_code": "KGM",
            "top_terms": ["картопля"],
            "size": 100,
            "median_price": 18.0,
            "n_anomalies": 1,
            "analysed": True,
        }
    ]
    wb = load_workbook(BytesIO(build_xlsx(request, run, cats, [anomaly], "Аудитор (a@b.ua)")))
    assert wb.sheetnames == ["Зведення", "Аномалії", "Групи"]
    rows = list(wb["Аномалії"].iter_rows(values_only=True))
    assert rows[1][:5] == (97.5, 180.0, "KGM", 18.0, 10.0)
    assert rows[1][12:14] == ("підтверджено", "завищена ціна")
    assert rows[1][14].endswith("UA-2026-09-01-000001-a")
    assert wb["Зведення"]["B5"].value == "1531"
