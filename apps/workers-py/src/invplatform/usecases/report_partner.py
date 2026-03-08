from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable, Optional, Sequence, TypedDict

from invplatform.usecases import report_totals


PARTNER_PERIODIC_MARKERS: tuple[str, ...] = (
    "חשבון תקופתי",
    "מקור-תקופתי",
    "חשבון מקור-תקופתי",
)


class PartnerTotalsResult(TypedDict, total=False):
    invoice_total: Optional[float]
    base_before_vat: Optional[float]
    invoice_vat: Optional[float]


def normalize_partner_text(text: str) -> str:
    return " ".join(text.split())


def parse_partner_amount_fragment(fragment: str) -> Optional[float]:
    cleaned = fragment.replace("{", " ").replace("}", " ")
    cleaned = " ".join(cleaned.split())
    match = re.search(r"(\d{1,2})\s*\.\s*([\d,]{3,})", cleaned)
    if match:
        token = f"{match.group(2)}.{match.group(1)}"
        amount = report_totals.parse_number(token)
        if amount is not None:
            return amount
    tokens = re.findall(r"[\d,]+\.\d{2}", cleaned)
    if tokens:
        return report_totals.parse_number(tokens[0])
    tokens = re.findall(r"[\d,]+", cleaned)
    if tokens:
        return report_totals.parse_number(tokens[0])
    return None


def extract_partner_amount(normalized: str, marker_pattern: str) -> Optional[float]:
    match = re.search(marker_pattern + r"(.{0,80})", normalized, flags=re.DOTALL)
    if not match:
        return None
    return parse_partner_amount_fragment(match.group(1))


def extract_partner_totals_from_text(text: str) -> PartnerTotalsResult:
    normalized = normalize_partner_text(text)
    total = extract_partner_amount(
        normalized,
        r"סה[\"״']?כ\s+חיובים\s+וזיכויים\s+לתקופת\s+החשבון\s+כולל\s+מע\"?מ",
    )
    if total is None:
        total = extract_partner_amount(normalized, r"סה[\"״']?כ\s+לתשלום")
    base = extract_partner_amount(
        normalized,
        r"סה[\"״']?כ\s+חיובי\s+החשבון\s+לא\s+כולל\s+מע\"?מ",
    )
    vat = extract_partner_amount(normalized, r"מע\"?מ%?\s*18")
    return {
        "invoice_total": total,
        "base_before_vat": base,
        "invoice_vat": vat,
    }


def extract_partner_totals_from_pdf(
    path: Path,
    *,
    have_pymupdf: bool,
    open_pdf: Callable[[Path], Any],
    periodic_markers: Sequence[str] = PARTNER_PERIODIC_MARKERS,
) -> PartnerTotalsResult:
    if not have_pymupdf:
        return {}
    try:
        doc = open_pdf(path)
    except Exception:
        return {}
    try:
        for page in doc:
            text = page.get_text("text")
            if not text:
                continue
            normalized = normalize_partner_text(text)
            if not all(marker in normalized for marker in ("חשבון", "תקופתי")):
                continue
            if not any(marker in normalized for marker in periodic_markers):
                continue
            totals = extract_partner_totals_from_text(text)
            if totals.get("invoice_total") is not None:
                return totals
    finally:
        doc.close()
    return {}
