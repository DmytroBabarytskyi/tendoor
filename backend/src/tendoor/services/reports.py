"""A3.2: звіт XLSX за результатами аналізу — зведення, аномалії з вердиктами, групи."""

from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

STATUS_UA = {
    "confirmed": "підтверджено",
    "not_anomaly": "аномалії немає",
    "needs_review": "потребує перевірки",
}
REASON_UA = {
    "overpriced": "завищена ціна",
    "underpriced": "занижена ціна (демпінг)",
    "unit_error": "помилка одиниці виміру",
    "data_error": "помилка в даних",
    "justified": "ціна обґрунтована",
    "other": "інше",
}
HEADER = PatternFill("solid", fgColor="DAE8FC")


def _sheet(ws, headers: list[str], rows: list[list], widths: list[int]) -> None:
    ws.append(headers)
    for cell in ws[1]:
        cell.font, cell.fill = Font(bold=True), HEADER
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for row in rows:
        ws.append(row)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def _factors(contributions: list | None, k: int = 3) -> str:
    """Три найбільші внески в ризик: «Сила відхилення від медіани групи +19; …»."""
    if not contributions:
        return ""
    return "; ".join(f"{c['label']} {c['points']:+.0f}" for c in contributions[:k])


def build_xlsx(request: dict, run: dict, categories: list[dict], anomalies: list[dict], author: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Зведення"
    m = run.get("metrics") or {}
    h = request.get("homogeneity_details") or {}
    summary = [
        ("Звіт системи Tendoor", ""),
        ("Сформовано", datetime.now().strftime("%d.%m.%Y %H:%M")),
        ("Автор", author),
        ("Аналіз №", request["id"]),
        ("Коди ДК 021", ", ".join(request["cpv_prefixes"])),
        ("Період оголошення", f"{request['date_from']:%d.%m.%Y} – {request['date_to']:%d.%m.%Y}"),
        ("Одиниці виміру", ", ".join(request["unit_codes"]) or "усі"),
        ("Індекс однорідності", h.get("index")),
        ("Версія конвеєра", run.get("pipeline_version")),
        ("Проаналізовано позицій", m.get("n_analysed")),
        ("Однорідних груп", m.get("n_groups")),
        ("Аномалій (високий ризик)", m.get("n_anomalies")),
        ("Ймовірних помилок даних", m.get("n_extreme")),
        ("Частка аномалій", m.get("anomaly_share")),
    ]
    for row in summary:
        ws.append(list(row))
    ws["A1"].font = Font(bold=True, size=14)
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 28, 60

    _sheet(
        wb.create_sheet("Аномалії"),
        [
            "Ризик",
            "Ймовірна помилка даних",
            "Ціна, грн",
            "Одиниця",
            "Медіана групи",
            "Відхилення, разів",
            "Предмет закупівлі",
            "Код ДК 021",
            "Замовник",
            "ЄДРПОУ",
            "Регіон",
            "Закупівля",
            "Дата",
            "Вердикт",
            "Причина",
            "Головні чинники ризику",
            "Посилання",
        ],
        [
            [
                float(a["risk_score"]) if a["risk_score"] is not None else None,
                "так" if a.get("is_extreme") else "",
                # ціна в одиниці моделі — та сама, що й у медіани групи (v2 перераховує фасовку)
                float(a["model_price"] if a.get("model_price") is not None else a["unit_price_base"]),
                a.get("model_unit") or a["base_unit_code"],
                float(a["median_price"]) if a["median_price"] is not None else None,
                round(a["price_ratio"], 2) if a["price_ratio"] else None,
                a["description"],
                a["cpv_code"],
                a["entity_name"],
                a["entity_edrpou"],
                a["entity_region"],
                a["tender_code"],
                a["date_published"].strftime("%d.%m.%Y"),
                STATUS_UA.get(a.get("verdict_status") or "", ""),
                REASON_UA.get(a.get("verdict_reason") or "", ""),
                _factors(a.get("contributions")),
                f"https://prozorro.gov.ua/tender/{a['tender_code']}",
            ]
            for a in anomalies
        ],
        [8, 10, 12, 9, 13, 12, 50, 12, 40, 11, 20, 24, 11, 18, 22, 48, 45],
    )
    _sheet(
        wb.create_sheet("Групи"),
        ["Код ДК 021", "Одиниця", "Ключові терміни", "Позицій", "Медіана, грн", "Аномалій"],
        [
            [
                c["cpv_code"],
                c["base_unit_code"],
                ", ".join(c["top_terms"]),
                c["size"],
                float(c["median_price"]) if c["median_price"] is not None else None,
                c["n_anomalies"],
            ]
            for c in categories
            if c["analysed"]
        ],
        [12, 9, 50, 10, 13, 10],
    )
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
