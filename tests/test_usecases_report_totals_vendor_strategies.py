import pytest

from invplatform.usecases import report_totals as totals_uc
from invplatform.usecases import report_vendor_strategies as vendor_uc

# Parsing marker constants (semantic anchors for totals/sections).
VAT_BEFORE_MARKER = 'מ"עמ ינפל'
VAT_MARKER = 'מע"מ'
TOTAL_MARKER = 'סה"כ'
INCLUDING_MARKER = "כולל"
MUNICIPAL_ARNONA = "ארנונה"
STINGTV_BREAKDOWN_MARKER = "ןובשחה טוריפ"
STINGTV_BREAKDOWN_END_MARKER = "עצבמב לולכ"
REVERSED_DETAILS_MARKER = ":םיטרפ"

# Description/statement label constants (invoice narrative sections).
PARTNER_PERIOD_DETAILS = "פירוט חיובים וזיכויים לתקופת החשבון"
PARTNER_ACCOUNT_CHARGES_TOTAL = 'סה"כ חיובי החשבון'

# Canonical vendor/municipal labels expected from strategy normalization.
PETAH_TIKVA_MUNICIPALITY = "עיריית פתח תקווה"
PARTNER_VENDOR = 'חברת פרטנר תקשורת בע"מ'
KEREN_VENDOR = "קרן-מדריכת הורים ותינוקות"

# Canonical invoice-for description labels.
ARNONA_BUSINESS = "ארנונה לעסקים"
ARNONA_GENERIC = "ארנונה"


@pytest.mark.parametrize("module", [totals_uc, vendor_uc], ids=["totals", "vendor"])
def test_shared_normalize_amount_token_edge_cases(module):
    assert module.normalize_amount_token(None) is None
    assert module.normalize_amount_token("abc") is None
    assert module.normalize_amount_token("1234.567") == "765.4321"


@pytest.mark.parametrize("module", [totals_uc, vendor_uc], ids=["totals", "vendor"])
def test_shared_parse_number_edge_cases(module):
    assert module.parse_number("1.2.3") is None


def test_report_totals_select_amount_edge_cases():
    # Year-like values should be ignored; low integers should fall back to first candidate.
    assert totals_uc.select_amount(["2025", "abc", "5", "9"]) == pytest.approx(5.0)
    # Invalid float tokens should be skipped while keeping valid >=10 fallback.
    assert totals_uc.select_amount(["8..1", "100"]) == pytest.approx(100.0)


def test_report_totals_numeric_and_amount_helpers_cover_percent_and_integer_fallback():
    text = "marker only"
    assert totals_uc.amount_near_markers(text, [r"marker"]) is None

    lines = [
        "header",
        f"{VAT_BEFORE_MARKER} 18%",
        "100.00",
        "neighbor 50% and 42",
    ]
    values = totals_uc.numeric_values_near_marker(lines, VAT_BEFORE_MARKER, window=2)
    assert 100.0 in values
    assert 18.0 not in values
    assert 50.0 not in values
    assert 42.0 in values

    assert totals_uc.amount_from_line_end("abc 12 34") == pytest.approx(34.0)
    assert totals_uc.amount_from_line_end("no digits here") is None


def test_report_totals_repeated_currency_and_marker_window_paths():
    assert totals_uc.repeated_currency_total(["0", "-1"]) is None
    assert totals_uc.repeated_currency_total(["12", "20"]) == pytest.approx(20.0)
    assert totals_uc.repeated_currency_total(["49", "55"]) == pytest.approx(55.0)

    lines_with_window_amount = [TOTAL_MARKER, VAT_MARKER, INCLUDING_MARKER, "120"]
    assert totals_uc.extract_total_from_total_with_vat_lines(
        lines_with_window_amount, []
    ) == pytest.approx(120.0)

    lines_without_window_amount = [TOTAL_MARKER, VAT_MARKER, INCLUDING_MARKER, "---"]
    assert totals_uc.extract_total_from_total_with_vat_lines(
        lines_without_window_amount, ["60", "60"]
    ) == pytest.approx(60.0)


def test_report_totals_extract_vat_from_percent_lines_paths():
    direct_line = [f"{VAT_MARKER} 17.00 18%"]
    assert totals_uc.extract_vat_from_percent_lines(
        direct_line,
        [],
        total=117.0,
        explicit_vat_rate=None,
    ) == pytest.approx(17.0)

    next_line = [f"{VAT_MARKER} 18%", "17.00"]
    assert totals_uc.extract_vat_from_percent_lines(
        next_line,
        [],
        total=117.0,
        explicit_vat_rate=None,
    ) == pytest.approx(17.0)

    rate_from_percent = [f"{VAT_MARKER} 18%"]
    assert totals_uc.extract_vat_from_percent_lines(
        rate_from_percent,
        ["100.00", "18.00", "200.00"],
        total=118.0,
        explicit_vat_rate=None,
    ) == pytest.approx(18.0)

    # Candidate exists but implied rate is too far from target rate (>1.0).
    assert (
        totals_uc.extract_vat_from_percent_lines(
            [f"{VAT_MARKER} 10%"],
            ["18.00"],
            total=118.0,
            explicit_vat_rate=None,
        )
        is None
    )


def test_report_totals_find_amount_before_marker_and_rate_helpers():
    lines = [
        "2025/01/01",
        "סהכ לתשלום",
        "300",
    ]
    assert totals_uc.find_amount_before_marker(lines, "סהכ לתשלום") == pytest.approx(
        300.0
    )

    percent_line = ["סהכ לתשלום 17%"]
    assert (
        totals_uc.find_amount_before_marker(
            percent_line, "סהכ לתשלום", prefer_inline=True
        )
        is None
    )

    assert totals_uc.vat_rate_estimate(100.0, 120.0) is None
    assert totals_uc.extract_vat_rate_from_text(None) is None


def test_report_totals_infer_totals_uses_marker_total_and_currency_difference():
    lines = [f"{TOTAL_MARKER} {VAT_MARKER} {INCLUDING_MARKER} 1,200.00"]
    text = """
    סה"כ יגבה: 1 200.00
    ₪ 1,200.00
    ₪ 1,000.00
    """
    totals = totals_uc.infer_totals(lines, text)
    assert totals["invoice_total"] == pytest.approx(1200.0)
    assert totals["invoice_vat"] == pytest.approx(200.0)


def test_report_totals_infer_totals_prefers_stingtv_breakdown_for_municipal_text():
    lines = ["irrelevant"]
    text = f"{MUNICIPAL_ARNONA} {STINGTV_BREAKDOWN_MARKER} 10 20 5 {STINGTV_BREAKDOWN_END_MARKER}"
    totals = totals_uc.infer_totals(lines, text)
    assert totals["municipal"] is True
    assert totals["breakdown_values"] == [10.0, 20.0, 5.0]
    assert totals["breakdown_sum"] == pytest.approx(35.0)
    assert totals["invoice_total"] == pytest.approx(35.0)
    assert totals["invoice_vat"] == pytest.approx(0.0)


def test_report_totals_infer_totals_municipal_without_stingtv_uses_generic_fallback():
    lines = ["header", "footer"]
    text = f"{MUNICIPAL_ARNONA}\n{TOTAL_MARKER} לתשלום 590.00\n₪ 590.00"
    totals = totals_uc.infer_totals(lines, text)
    assert totals["municipal"] is True
    assert totals["breakdown_sum"] is None
    assert totals["breakdown_values"] == []
    assert totals["invoice_total"] == pytest.approx(590.0)
    assert totals["invoice_vat"] == pytest.approx(0.0)


def test_vendor_strategies_normalization_and_detection_edge_cases():
    assert vendor_uc.normalize_invoice_for_value("1234") is None
    assert (
        vendor_uc.normalize_invoice_for_value(f"{ARNONA_BUSINESS} נכס 7")
        == ARNONA_BUSINESS
    )
    assert vendor_uc.normalize_invoice_for_value("ארנונה כללית") == ARNONA_GENERIC

    assert vendor_uc.detect_known_vendor(None) is None
    assert vendor_uc.has_public_transport_marker("rav kav טעינה")
    assert not vendor_uc.has_public_transport_marker("non matching text")
    assert not vendor_uc.looks_like_petah_tikva_municipality("פתח תק")


def test_vendor_strategies_infer_invoice_from_multiple_branches():
    assert (
        vendor_uc.infer_invoice_from(['חברת דוגמה בע"מ'], "פרטנר שירותים")
        == PARTNER_VENDOR
    )
    assert (
        vendor_uc.infer_invoice_from(["first line"], "קרן מדריכת הורים ותינוקות שירות")
        == KEREN_VENDOR
    )
    assert (
        vendor_uc.infer_invoice_from(["first line"], "מאת ספק כלשהו: לכבוד לקוח")
        == "ספק כלשהו"
    )
    assert (
        vendor_uc.infer_invoice_from(["first line"], "עריית פתח תקווה מחלקת גבייה")
        == "עיריית פתח תקווה מחלקת גבייה"
    )
    assert (
        vendor_uc.infer_invoice_from(["first line"], "הווקת חתפ רשות מקומית")
        == PETAH_TIKVA_MUNICIPALITY
    )


def test_vendor_strategies_partner_ofek_stingtv_and_just_simple_paths():
    header_only_lines = [PARTNER_PERIOD_DETAILS, TOTAL_MARKER]
    assert (
        vendor_uc.extract_partner_invoice_for(header_only_lines)
        == PARTNER_PERIOD_DETAILS
    )

    raw_segment = (
        f"{PARTNER_PERIOD_DETAILS} 2מנויי סלולר "
        "1מנוי תמסורת 123-456 תנועות כלליות בחשבון הלקוח "
        f"{PARTNER_ACCOUNT_CHARGES_TOTAL}"
    )
    assert (
        vendor_uc.extract_partner_invoice_for([], raw_segment)
        == "2 מנויי סלולר | 1 מנוי תמסורת 123-456 | תנועות כלליות בחשבון הלקוח"
    )

    empty_segment = f"{PARTNER_PERIOD_DETAILS} טקסט חופשי ללא ממצאים {PARTNER_ACCOUNT_CHARGES_TOTAL}"
    assert (
        vendor_uc.extract_partner_invoice_for([], empty_segment)
        == PARTNER_PERIOD_DETAILS
    )

    assert (
        vendor_uc.extract_ofek_invoice_for("דצמבר חודש חוג דצמבר חודש חוג")
        == "חוג חודש דצמבר"
    )
    assert vendor_uc.extract_stingtv_invoice_for("אין מונחים כאן") is None
    assert vendor_uc.extract_stingtv_invoice_for(
        "שירותי תוכן בינלאומיים ספריות וערוצי פרימיום"
    ) == ("שירותי תוכן בינלאומיים | ספריות וערוצי פרימיום")
    assert vendor_uc.extract_stingtv_breakdown("אין סעיף") == []
    assert vendor_uc.extract_stingtv_breakdown("ןובשחה טוריפ 10 20.5 -3 Sample") == [
        10.0,
        20.5,
        -3.0,
    ]

    assert vendor_uc.extract_just_simple_invoice_for([], None) is None
    assert vendor_uc.extract_just_simple_invoice_for(["random"], "random text") is None


def test_vendor_strategies_infer_invoice_for_fallback_routes():
    details_marker_lines = [
        REVERSED_DETAILS_MARKER,
        "תיאור שירות",
        "מסלול חודשי",
        TOTAL_MARKER,
    ]
    assert (
        vendor_uc.infer_invoice_for(details_marker_lines, None)
        == "תיאור שירות | מסלול חודשי"
    )

    detail_label_lines = [
        "פירוט החיוב: נכס 123",
        "מספר זיהוי 1",
        "שלטים 2026",
    ]
    assert vendor_uc.infer_invoice_for(detail_label_lines, None) == "שלטים 2026"

    time_range_lines = [
        "שעות פעילות עבור 10:00 - 11:00",
        "חיוב עבור שירות - חודשי",
    ]
    assert (
        vendor_uc.infer_invoice_for(time_range_lines, None) == "חיוב עבור שירות - חודשי"
    )

    assert vendor_uc.infer_invoice_for(["x"], "ארנונה לעסקים מס 7") == ARNONA_BUSINESS
    assert vendor_uc.infer_invoice_for(["x"], "ארנונה כללית") == ARNONA_GENERIC
