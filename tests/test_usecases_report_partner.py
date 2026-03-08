import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "apps" / "workers-py" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from invplatform.usecases import report_partner  # noqa: E402


def test_extract_partner_totals_from_text_parses_markers():
    text = """
    חשבון תקופתי
    סה"כ חיובים וזיכויים לתקופת החשבון כולל מע"מ 1,151.00
    סה"כ חיובי החשבון לא כולל מע"מ 975.42
    מע"מ 18 175.58
    """
    totals = report_partner.extract_partner_totals_from_text(text)
    assert totals["invoice_total"] == 1151.0
    assert totals["base_before_vat"] == 975.42
    assert totals["invoice_vat"] == 175.58


def test_extract_partner_totals_from_pdf_uses_dependency_seam():
    class _Page:
        def __init__(self, text):
            self._text = text

        def get_text(self, kind):
            assert kind == "text"
            return self._text

    class _Doc:
        def __init__(self, pages):
            self._pages = pages

        def __iter__(self):
            return iter(self._pages)

        def close(self):
            return None

    doc = _Doc(
        [
            _Page("not relevant"),
            _Page(
                "חשבון תקופתי\n"
                'סה"כ חיובים וזיכויים לתקופת החשבון כולל מע"מ 1,151.00\n'
                'סה"כ חיובי החשבון לא כולל מע"מ 975.42\n'
                'מע"מ 18 175.58'
            ),
        ]
    )
    totals = report_partner.extract_partner_totals_from_pdf(
        Path("partner.pdf"),
        have_pymupdf=True,
        open_pdf=lambda _path: doc,
    )
    assert totals["invoice_total"] == 1151.0
    assert totals["base_before_vat"] == 975.42
    assert totals["invoice_vat"] == 175.58


def test_extract_partner_totals_from_pdf_returns_empty_without_pymupdf():
    totals = report_partner.extract_partner_totals_from_pdf(
        Path("partner.pdf"),
        have_pymupdf=False,
        open_pdf=lambda _path: None,
    )
    assert totals == {}
