import sys
from dataclasses import asdict
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "apps" / "workers-py" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from invplatform.cli import invoices_report as report  # noqa: E402
from invplatform.usecases import report_pipeline  # noqa: E402


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "invoices"


def test_parse_path_calls_both_steps():
    called = []

    def _parse(path, debug):
        called.append(("parse", path.name, debug))
        return {"id": path.name}

    def _split(path, record, debug):
        called.append(("split", path.name, record["id"], debug))
        return [record, {"id": "x"}]

    result = report_pipeline.parse_path(
        Path("a.pdf"),
        debug=True,
        parse_invoice_fn=_parse,
        split_municipal_multi_invoice_fn=_split,
    )
    assert result == [{"id": "a.pdf"}, {"id": "x"}]
    assert called == [("parse", "a.pdf", True), ("split", "a.pdf", "a.pdf", True)]


def test_parse_paths_aggregates_multiple_inputs():
    result = report_pipeline.parse_paths(
        [Path("a.pdf"), Path("b.pdf")],
        debug=False,
        parse_invoice_fn=lambda path, debug: {"id": path.name, "debug": debug},
        split_municipal_multi_invoice_fn=lambda _path, record, _debug: [record],
    )
    assert result == [
        {"id": "a.pdf", "debug": False},
        {"id": "b.pdf", "debug": False},
    ]


@pytest.mark.parametrize(
    "fixture_name",
    [
        "municipal_8Uhc.txt",
        "partner_postpaid_998018687.txt",
        "stingtv_09_2025.txt",
        "ravkav_topup.txt",
    ],
)
def test_pipeline_parse_path_matches_cli_parse_invoices(monkeypatch, fixture_name):
    text = (FIXTURES_DIR / fixture_name).read_text(encoding="utf-8")
    lines = report.extract_lines(text)
    monkeypatch.setattr(report, "extract_text", lambda _path: text)
    monkeypatch.setattr(report, "extract_text_with_pymupdf", lambda _path: text)
    monkeypatch.setattr(report, "extract_lines", lambda _text: lines)
    monkeypatch.setattr(
        report, "file_sha256", lambda _path: f"fixture-hash-{fixture_name}"
    )
    path = Path(fixture_name).with_suffix(".pdf")
    via_pipeline = report_pipeline.parse_path(
        path,
        debug=False,
        parse_invoice_fn=lambda p, d: report.parse_invoice(p, debug=d),
        split_municipal_multi_invoice_fn=lambda p,
        rec,
        d: report.split_municipal_multi_invoice(
            p,
            rec,
            debug=d,
        ),
    )
    via_cli = report.parse_invoices(path, debug=False)
    assert [asdict(rec) for rec in via_pipeline] == [asdict(rec) for rec in via_cli]
