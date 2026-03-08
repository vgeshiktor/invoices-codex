import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "apps" / "workers-py" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from invplatform.usecases import duplicate_policy  # noqa: E402
from invplatform.usecases import pdf_download  # noqa: E402
from invplatform.usecases import report_io  # noqa: E402
from invplatform.usecases import pdf_verification  # noqa: E402
from invplatform.usecases import provider_runner  # noqa: E402


def test_pdf_download_supports_yes_headers_and_fallback():
    calls = []

    class Resp:
        def __init__(self, status, headers, content):
            self.status_code = status
            self.headers = headers
            self.content = content

    responses = [
        Resp(403, {"Content-Type": "application/pdf"}, b""),
        Resp(
            200,
            {
                "Content-Type": "application/pdf",
                "Content-Disposition": 'attachment; filename="inv"',
            },
            b"%PDF-content",
        ),
    ]

    def _get(url, headers, timeout):
        calls.append(headers)
        return responses.pop(0)

    result = pdf_download.download_direct_pdf(
        "https://svc.yes.co.il/invoice",
        request_get=_get,
        referer="https://origin",
        include_yes_headers=True,
        fallback_without_referer_on_403=True,
    )
    assert result == ("inv.pdf", b"%PDF-content")
    assert calls[0]["Referer"] == "https://origin"
    assert calls[0]["Origin"] == "https://www.yes.co.il"
    assert "Referer" not in calls[1]


def test_pdf_verification_variants():
    graph_ok, _ = pdf_verification.decide_pdf_relevance_graph(
        "path",
        pdf_keyword_stats=lambda _p: {"pos_hits": 0, "neg_terms": []},
        trusted_hint=True,
    )
    assert graph_ok

    gmail_ok, _ = pdf_verification.decide_pdf_relevance_gmail(
        "path",
        pdf_keyword_stats=lambda _p: {
            "pos_hits": 1,
            "neg_hits": 0,
            "strong_hits": 0,
            "amount_hint": False,
            "invoice_id_hint": False,
        },
        have_pymupdf=True,
        trusted_hint=False,
    )
    assert not gmail_ok


def test_provider_runner_execute_provider_paths(monkeypatch):
    assert provider_runner.provider_argv(["python", "-m", "mod", "--x"]) == ["--x"]
    assert provider_runner.provider_argv(["--x"]) == ["--x"]
    invocation = provider_runner.invocation_from_command(
        ["python3", "-m", "pkg.mod", "--flag"]
    )
    assert invocation.python_bin == "python3"
    assert invocation.module == "pkg.mod"
    assert invocation.argv == ["--flag"]
    assert invocation.to_command() == ["python3", "-m", "pkg.mod", "--flag"]

    monkeypatch.setattr(provider_runner, "resolve_runner", lambda _n: lambda _a: 0)
    assert provider_runner.execute_provider("gmail", ["--x"]).returncode == 0
    assert provider_runner.execute_provider("gmail", invocation).returncode == 0

    monkeypatch.setattr(
        provider_runner,
        "resolve_runner",
        lambda _n: (lambda _a: (_ for _ in ()).throw(SystemExit(7))),
    )
    assert provider_runner.execute_provider("gmail", ["--x"]).returncode == 7

    monkeypatch.setattr(
        provider_runner,
        "resolve_runner",
        lambda _n: (lambda _a: (_ for _ in ()).throw(RuntimeError("boom"))),
    )
    res = provider_runner.execute_provider("gmail", ["--x"])
    assert res.returncode == 1
    assert "boom" in (res.error or "")


def test_duplicate_policy_helpers():
    hashes = set()
    hash_to_path = {}
    assert not duplicate_policy.duplicate_by_hash("a", hashes)
    duplicate_policy.remember_hash("a", "/tmp/a.pdf", hashes, hash_to_path)
    assert duplicate_policy.duplicate_by_hash("a", hashes)
    assert duplicate_policy.duplicate_of_hash("a", hash_to_path) == "/tmp/a.pdf"

    fps = set()
    fp_to_path = {}
    assert not duplicate_policy.duplicate_by_text_fingerprint("fp", fps)
    duplicate_policy.remember_text_fingerprint("fp", "/tmp/a.pdf", fps, fp_to_path)
    assert duplicate_policy.duplicate_by_text_fingerprint("fp", fps)
    assert duplicate_policy.duplicate_of_text("fp", fp_to_path) == "/tmp/a.pdf"

    stems = set()
    assert not duplicate_policy.duplicate_by_stem("stem", stems)
    duplicate_policy.remember_stem("stem", stems)
    assert duplicate_policy.duplicate_by_stem("stem", stems)


def test_report_io_writes_json_and_csv(tmp_path):
    payload_path = tmp_path / "out" / "payload.json"
    report_io.write_json(payload_path, {"ok": True})
    assert '"ok": true' in payload_path.read_text(encoding="utf-8")

    csv_path = tmp_path / "out" / "rows.csv"
    report_io.write_dict_rows_csv(
        csv_path,
        rows=[{"id": "1", "name": "Invoice"}],
        fields=["id", "name"],
    )
    content = csv_path.read_text(encoding="utf-8")
    assert "id,name" in content
    assert "1,Invoice" in content
