from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import List, Optional

from ..adapters.base import MailAdapter, MessageMeta
from ..domain.relevance import should_consider_message

SENT_FOLDERS = {"sent", "sentitems", "sent items", "sentitemsfolder"}


@dataclass
class FetchConfig:
    start_date: str
    end_date: str
    verify: bool = False
    exclude_sent: bool = True
    max_messages: int = 500


def _parse_date_bound(value: str) -> datetime:
    d = date.fromisoformat(value)
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _parse_received(value: str) -> Optional[datetime]:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    parsed: Optional[datetime] = None
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(candidate, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_sent_message(message: MessageMeta) -> bool:
    folder = (message.folder or "").strip().lower()
    return folder in SENT_FOLDERS


def _message_has_pdf_attachment(adapter: MailAdapter, message: MessageMeta) -> bool:
    try:
        for att in adapter.iter_attachments(message):
            content_type = (att.content_type or "").lower()
            name = (att.name or "").lower()
            if "pdf" in content_type or name.endswith(".pdf"):
                return True
    except Exception:
        return False
    return False


def fetch_invoices(adapter: MailAdapter, config: FetchConfig) -> List[MessageMeta]:
    """Fetch invoice-like messages for a date range from a provider adapter."""
    start = _parse_date_bound(config.start_date)
    end = _parse_date_bound(config.end_date)

    matched: List[MessageMeta] = []
    for message in adapter.iter_messages():
        received_at = _parse_received(message.received)
        if received_at is None or received_at < start or received_at >= end:
            continue
        if config.exclude_sent and _is_sent_message(message):
            continue
        has_pdf_attachment = False
        if message.has_attachments:
            has_pdf_attachment = _message_has_pdf_attachment(adapter, message)
        if has_pdf_attachment or should_consider_message(message.subject, message.preview):
            matched.append(message)

    matched.sort(key=lambda msg: _parse_received(msg.received) or start, reverse=True)
    if config.max_messages > 0:
        return matched[: config.max_messages]
    return matched
