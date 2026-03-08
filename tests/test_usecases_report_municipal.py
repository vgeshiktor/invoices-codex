import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "apps" / "workers-py" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from invplatform.usecases import report_municipal  # noqa: E402


def test_find_municipal_invoice_id_detects_neighbor_label():
    lines = ["עבור גן ילדים", "10200570020", "עוד שורה"]
    invoice_id, invoice_for = report_municipal.find_municipal_invoice_id(lines)
    assert invoice_id == "10200570020"
    assert invoice_for == "עבור גן ילדים"


def test_extract_municipal_breakdown_handles_discount_lines():
    lines = [
        "6010.90 חיוב תקופתי ארנונה",
        "42.10 הנחת גביה",
    ]
    values = report_municipal.extract_municipal_breakdown(lines)
    assert values == [pytest.approx(6010.90), pytest.approx(-42.10)]


def test_extract_amount_from_label_reads_line_words():
    class _Page:
        def get_text(self, kind):
            assert kind == "words"
            return [
                (10.0, 100.0, 11.0, 101.0, 'סה"כ', 0, 0, 0),
                (20.0, 100.0, 21.0, 101.0, "יגבה", 0, 0, 1),
                (70.0, 100.0, 71.0, 101.0, "1,234.50", 0, 0, 2),
            ]

    amount = report_municipal.extract_amount_from_label(_Page(), ["יגבה"])
    assert amount == pytest.approx(1234.50)
