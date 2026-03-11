from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "apps" / "workers-py" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from invplatform.usecases import report_totals as totals  # noqa: E402


def test_normalize_and_select_amount_edge_cases() -> None:
    assert totals.normalize_amount_token(None) is None
    assert totals.normalize_amount_token("abc") is None
    assert totals.normalize_amount_token("12.345") == "345.12"
    assert totals.normalize_amount_token("123.456") == "654.321"
    assert totals.select_amount(["bad", "2024", "1", "9"]) == pytest.approx(1.0)


def test_amount_near_markers_and_amount_from_line_end_decimal_priority() -> None:
    assert totals.amount_near_markers("marker only", [r"marker"]) is None
    assert totals.amount_from_line_end("line 15 42.70") == pytest.approx(42.70)


def test_repeated_currency_total_fallback_paths() -> None:
    assert totals.repeated_currency_total(["0", "-5", "bad"]) is None
    assert totals.repeated_currency_total(["10", "20", "30"]) == pytest.approx(30.0)
    assert totals.repeated_currency_total(["10", "55", "51"]) == pytest.approx(55.0)


def test_extract_total_from_total_with_vat_lines_paths() -> None:
    direct = ['סה"כ כולל מע"מ 120.50']
    assert totals.extract_total_from_total_with_vat_lines(direct, []) == pytest.approx(
        120.5
    )

    window_based = ['סה"כ', 'מע"מ', "כולל", "100", "200"]
    assert totals.extract_total_from_total_with_vat_lines(
        window_based, []
    ) == pytest.approx(100.0)


def test_extract_vat_from_percent_lines_and_threshold_guard() -> None:
    lines = ['מע"מ 18% סיכום 50.00']
    assert totals.extract_vat_from_percent_lines(
        lines,
        ["50.00"],
        total=118.0,
        explicit_vat_rate=None,
    ) == pytest.approx(50.0)

    assert (
        totals.extract_vat_from_percent_lines(
            ['מע"מ 18%'],
            ["5.00"],
            total=118.0,
            explicit_vat_rate=None,
        )
        is None
    )


def test_vat_rate_and_vat_text_edge_cases() -> None:
    assert totals.vat_rate_estimate(10.0, 10.0) is None
    assert totals.extract_vat_rate_from_text(None) is None


def test_infer_totals_debug_and_spaced_total_token(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = totals.infer_totals(
        ["header"], 'סה"כ יגבה: 1 234.50', debug=True, label="cov"
    )
    output = capsys.readouterr().out
    assert "[debug][cov]" in output
    assert result["invoice_total"] == pytest.approx(1234.5)


def test_infer_totals_reversed_block_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    original = totals.parse_number

    def fake_parse(raw: str | None):  # type: ignore[no-untyped-def]
        if raw == "123":
            return None
        if raw == "321":
            return 321.0
        return original(raw)

    monkeypatch.setattr(totals, "parse_number", fake_parse)
    result = totals.infer_totals(["header"], "סהכ יגבה: abc123\n4")
    assert result["invoice_total"] == pytest.approx(321.0)


def test_infer_totals_igbe_secondary_pattern_and_reversed_currency_marker() -> None:
    from_secondary = totals.infer_totals(["x"], "סהכ יגבה פרטים 555.40")
    assert from_secondary["invoice_total"] == pytest.approx(555.4)

    from_reversed_marker = totals.infer_totals(["x"], '₪ 700.00 כ"הס')
    assert from_reversed_marker["invoice_total"] == pytest.approx(700.0)


def test_infer_totals_prefers_currency_when_tiny_total() -> None:
    result = totals.infer_totals(["x"], 'סה"כ יגבה: 1\n₪ 118.00')
    assert result["invoice_total"] == pytest.approx(118.0)


def test_infer_totals_vat_pattern_and_currency_refinement() -> None:
    text = 'סה"כ: 118 סה"כ מע"מ 30 ₪ 100'
    result = totals.infer_totals(["row"], text)
    assert result["invoice_total"] == pytest.approx(118.0)
    assert result["invoice_vat"] == pytest.approx(18.0)


def test_infer_totals_vat_scan_skips_maml_and_uses_next_line() -> None:
    lines = ['מ"עמל הערה', 'מ"עמ 18']
    result = totals.infer_totals(lines, 'סה"כ: 118')
    assert result["invoice_total"] == pytest.approx(118.0)
    assert result["invoice_vat"] == pytest.approx(18.0)


def test_infer_totals_vat_reset_when_above_total_then_base_diff_fallback() -> None:
    lines = ['מ"עמ ינפל 100']
    text = 'סה"כ: 118 סה"כ מע"מ 200'
    result = totals.infer_totals(lines, text)
    assert result["invoice_total"] == pytest.approx(118.0)
    assert result["invoice_vat"] == pytest.approx(18.0)
