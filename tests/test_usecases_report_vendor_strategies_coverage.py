from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "apps" / "workers-py" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from invplatform.usecases import report_vendor_strategies as strategies  # noqa: E402


def test_numeric_parsers_and_basic_none_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    assert strategies.normalize_amount_token(None) is None
    assert strategies.normalize_amount_token("abc") is None
    assert strategies.normalize_amount_token("12.345") == "345.12"
    assert strategies.normalize_amount_token("1,2,3") == "123"
    assert strategies.normalize_amount_token("12,34") == "12.34"
    assert strategies.parse_number("bad") is None

    monkeypatch.setattr(strategies, "normalize_amount_token", lambda _raw: "1.2.3")
    assert strategies.parse_number("ignored") is None

    assert strategies.normalize_invoice_for_value(None) is None
    assert strategies.detect_known_vendor(None) is None


def test_public_transport_and_petah_tikva_negative_paths() -> None:
    assert strategies.looks_like_petah_tikva_municipality(None) is False
    assert strategies.looks_like_petah_tikva_municipality("פתח תקווה בלבד") is False
    assert strategies.has_public_transport_marker("סתם טקסט") is False


def test_infer_invoice_from_meyet_and_municipality_and_candidate_fallback() -> None:
    lines = ['חברת דוגמה בע"מ', "שורה שניה"]
    assert (
        strategies.infer_invoice_from(lines, "מאת חברה מצוינת: לכבוד לקוח שם אחר")
        == "חברה מצוינת"
    )

    assert strategies.infer_invoice_from(lines, "עריית פתח תקווה") == "עיריית פתח תקווה"

    assert strategies.infer_invoice_from(lines, "טקסט ללא התאמה") == 'חברת דוגמה בע"מ'


def test_extract_partner_invoice_for_from_lines_and_default() -> None:
    lines = [
        "כותרת",
        "פירוט חיובים וזיכויים לתקופת החשבון",
        "חיוב שירות A",
        "זיכוי שירות B",
        'סה"כ',
    ]
    assert (
        strategies.extract_partner_invoice_for(lines, None)
        == "חיוב שירות A | זיכוי שירות B"
    )

    lines_without_details = [
        "כותרת",
        "פירוט חיובים וזיכויים לתקופת החשבון",
        'סה"כ',
    ]
    assert (
        strategies.extract_partner_invoice_for(lines_without_details, None)
        == "פירוט חיובים וזיכויים לתקופת החשבון"
    )


def test_extract_partner_invoice_for_raw_text_default_path() -> None:
    raw_text = (
        "פירוט חיובים וזיכויים לתקופת החשבון פרטים כלליים בלבד " 'סה"כ חיובי החשבון'
    )
    assert (
        strategies.extract_partner_invoice_for([], raw_text)
        == "פירוט חיובים וזיכויים לתקופת החשבון"
    )


def test_extract_stingtv_breakdown_empty_paths() -> None:
    assert strategies.extract_stingtv_breakdown(None) == []
    assert strategies.extract_stingtv_breakdown("טקסט ללא מרקר") == []


def test_extract_just_simple_invoice_for_paths() -> None:
    assert strategies.extract_just_simple_invoice_for([], None) is None

    lines = [
        "JUST SIMPLE LTD",
        "תאור",
        "תפעול",
        "פנסיוני",
        "שוטף",
        "12/25",
        "כמות",
    ]
    text = "JUST SIMPLE LTD חשבונית"
    assert (
        strategies.extract_just_simple_invoice_for(lines, text)
        == "תפעול פנסיוני- שוטף 12/25"
    )


def test_infer_invoice_for_details_marker_and_tail_and_fallbacks() -> None:
    details_lines = [
        "header",
        ":םיטרפ",
        "פרט א",
        "פרט ב",
        "טקמ",
    ]
    assert strategies.infer_invoice_for(details_lines, "טקסט") == "פרט א | פרט ב"

    tail_lines = ["פירוט החיוב: שירות תמיכה"]
    assert strategies.infer_invoice_for(tail_lines, "טקסט") == "שירות תמיכה"

    time_range_lines = ["משהו עבור 10:00 - 11:00"]
    assert (
        strategies.infer_invoice_for(time_range_lines, "ארנונה לעסקים לתשלום")
        == "ארנונה לעסקים"
    )
    assert strategies.infer_invoice_for(time_range_lines, "ארנונה לתשלום") == "ארנונה"
