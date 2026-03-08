from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
from typing import Optional, Set


def now_utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def now_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")


def normalize_myinvoice_url(url: str) -> str:
    s = (url or "").strip()
    s = s.replace("\\?", "?").replace("\\&", "&").replace("\\=", "=")
    s = s.replace("://myinvoice.bezeq.co.il//?", "://myinvoice.bezeq.co.il/?")
    s = re.sub(r"(://myinvoice\.bezeq\.co\.il)/+(?=\?)", r"\1/", s)
    return s


def is_retryable_reason(reason: str) -> bool:
    text = (reason or "").lower()
    return "_fail" in text or "timeout" in text or "rate" in text


def load_cached_processed_message_ids(report_path: Optional[str]) -> Set[str]:
    if not report_path:
        return set()
    p = pathlib.Path(report_path)
    if not p.exists():
        return set()
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if not isinstance(payload, dict):
        return set()

    ids: Set[str] = set()

    for row in payload.get("saved", []) or []:
        if isinstance(row, dict):
            mid = row.get("id")
            if isinstance(mid, str) and mid:
                ids.add(mid)

    for row in payload.get("rejected", []) or []:
        if not isinstance(row, dict):
            continue
        mid = row.get("id")
        if not (isinstance(mid, str) and mid):
            continue
        reason = row.get("reason") or ""
        if is_retryable_reason(str(reason)):
            continue
        ids.add(mid)

    for row in payload.get("report", []) or []:
        if not isinstance(row, dict):
            continue
        mid = row.get("msg_id") or row.get("id")
        if not (isinstance(mid, str) and mid):
            continue
        reject = row.get("reject") or ""
        if is_retryable_reason(str(reject)):
            continue
        ids.add(mid)

    return ids
