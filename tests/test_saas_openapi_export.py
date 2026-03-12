from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")


def test_export_writes_openapi_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from invplatform.cli import saas_openapi_export

    output = tmp_path / "saas-openapi.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "saas_openapi_export",
            "--database-url",
            "sqlite://",
            "--storage-url",
            "local://./data/saas_storage",
            "--output",
            str(output),
        ],
    )

    saas_openapi_export.main()
    assert output.exists()

    body = json.loads(output.read_text(encoding="utf-8"))
    assert body["info"]["title"] == "Invoices SaaS API"
    assert body["info"]["version"] == "0.1.0"
    assert "/v1/dashboard/summary" in body["paths"]
    assert "/v1/providers" in body["paths"]
    assert body["components"]["securitySchemes"]["ApiKeyAuth"]["type"] == "apiKey"
