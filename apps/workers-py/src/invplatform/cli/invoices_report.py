from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import html
import json
import logging
import os
import re
from dataclasses import dataclass, asdict, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, cast

from invplatform.usecases import (
    report_municipal,
    report_partner,
    report_pipeline,
    report_parser,
    report_splitter,
    report_totals,
    report_vendor_strategies,
)

try:
    from pdfminer.high_level import extract_text
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "Missing dependency: pdfminer.six is required for invoice parsing. "
        "Install it with `pip install pdfminer.six` or add it to your environment."
    ) from exc

try:
    import fitz  # type: ignore[import-untyped]

    HAVE_PYMUPDF = True
except ModuleNotFoundError:
    HAVE_PYMUPDF = False


Amount = Optional[float]

KNOWN_VENDOR_MARKERS = report_vendor_strategies.KNOWN_VENDOR_MARKERS
PETAH_TIKVA_KEYWORDS = report_vendor_strategies.PETAH_TIKVA_KEYWORDS
PETAH_TIKVA_MUNICIPAL_MARKERS = report_vendor_strategies.PETAH_TIKVA_MUNICIPAL_MARKERS
PUBLIC_TRANSPORT_HEBREW_MARKERS = report_vendor_strategies.PUBLIC_TRANSPORT_HEBREW_MARKERS
PUBLIC_TRANSPORT_LATIN_MARKERS = report_vendor_strategies.PUBLIC_TRANSPORT_LATIN_MARKERS
PUBLIC_TRANSPORT_INVOICE_FOR = report_vendor_strategies.PUBLIC_TRANSPORT_INVOICE_FOR

PDF_REPORT_COLUMNS: Tuple[Tuple[str, str, float, int], ...] = (
    ("invoice_id", "Invoice No.", 0.10, 1),
    ("invoice_date", "Invoice Date", 0.12, 1),
    ("invoice_from", "Vendor", 0.19, 2),
    ("invoice_for", "Description", 0.23, 2),
    ("base_before_vat", "Subtotal (Before VAT)", 0.14, 2),
    ("invoice_vat", "VAT Amount", 0.11, 2),
    ("invoice_total", "Total Amount", 0.11, 2),
)


@dataclass
class InvoiceRecord:
    source_file: str
    invoice_id: Optional[str] = None
    invoice_date: Optional[str] = None
    invoice_from: Optional[str] = None
    invoice_for: Optional[str] = None
    base_before_vat: Amount = None
    invoice_vat: Amount = None
    invoice_total: Amount = None
    currency: Optional[str] = "₪"
    notes: Optional[str] = None
    breakdown_sum: Amount = None
    breakdown_values: Optional[List[float]] = None
    vat_rate: Optional[float] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    period_label: Optional[str] = None
    due_date: Optional[str] = None
    category: Optional[str] = None
    category_confidence: Optional[float] = None
    category_rule: Optional[str] = None
    reference_numbers: Optional[List[str]] = None
    data_source: Optional[str] = None
    parse_confidence: Optional[float] = None
    municipal: Optional[bool] = None
    duplicate_hash: Optional[str] = None

    def to_csv_row(self, fields: Sequence[str]) -> List[str]:
        row = []
        data = asdict(self)
        for field in fields:
            value = data.get(field)
            if isinstance(value, float):
                row.append(f"{value:.2f}")
            elif isinstance(value, bool):
                row.append("true" if value else "false")
            elif isinstance(value, (list, dict)):
                row.append(json.dumps(value, ensure_ascii=False))
            elif value is None:
                row.append("")
            else:
                row.append(str(value))
        return row


def normalize_amount_token(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    sign = ""
    stripped = raw.strip()
    if stripped.startswith("-"):
        sign = "-"
    token = "".join(ch for ch in raw if ch.isdigit() or ch in ".,")
    if not token:
        return None
    body = token.lstrip("-")
    if re.match(r"^\d+\.\d{3}$", body):
        head, tail = body.split(".")
        if len(head) <= 2:
            swapped = tail + "." + head
        else:
            swapped = body[::-1]
        token = ("-" if token.startswith("-") else "") + swapped
    if "," in token and "." in token:
        token = token.replace(",", "")
    elif token.count(",") > 1:
        token = token.replace(",", "")
    elif token.count(",") == 1 and "." not in token:
        token = token.replace(",", ".")
    return sign + token


def parse_number(raw: Optional[str]) -> Amount:
    token = normalize_amount_token(raw)
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def select_amount(tokens: Iterable[str]) -> Amount:
    candidates = []
    for token in tokens:
        normalized = normalize_amount_token(token)
        if not normalized:
            continue
        if normalized.isdigit() and len(normalized) == 4 and normalized.startswith("20"):
            continue
        try:
            amount = float(normalized)
        except ValueError:
            continue
        candidates.append((amount, normalized))
    if not candidates:
        return None
    for amount, normalized in candidates:
        if "." in normalized and len(normalized.split(".")[-1]) == 2:
            return amount
    for amount, normalized in candidates:
        if "." in normalized:
            return amount
    for amount, _ in candidates:
        if amount >= 10:
            return amount
    return candidates[0][0]


MONTH_NAME_MAP = {
    "ינואר": 1,
    "פברואר": 2,
    "מרץ": 3,
    "מרס": 3,
    "אפריל": 4,
    "מאי": 5,
    "יוני": 6,
    "יולי": 7,
    "אוגוסט": 8,
    "ספטמבר": 9,
    "ספטמבער": 9,
    "אוקטובר": 10,
    "נובמבר": 11,
    "דצמבר": 12,
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

MONTH_LABELS_HE = {
    1: "ינואר",
    2: "פברואר",
    3: "מרץ",
    4: "אפריל",
    5: "מאי",
    6: "יוני",
    7: "יולי",
    8: "אוגוסט",
    9: "ספטמבר",
    10: "אוקטובר",
    11: "נובמבר",
    12: "דצמבר",
}


def normalize_date_token(token: str, default_day: Optional[int] = None) -> Optional[str]:
    if not token:
        return None
    candidate = (
        token.strip().replace("\\", "-").replace("/", "-").replace(".", "-").replace(",", "-")
    )
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y", "%m-%d-%Y", "%d-%b-%Y", "%d-%b-%y"):
        try:
            dt = datetime.strptime(candidate, fmt)
            if dt.year < 100:
                dt = dt.replace(year=2000 + dt.year)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    # month-year patterns
    m = re.match(r"(\d{4})-(\d{1,2})$", candidate)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        day = default_day or 1
        day = min(day, calendar.monthrange(year, month)[1])
        return date(year, month, day).strftime("%Y-%m-%d")
    m = re.match(r"(\d{1,2})-(\d{4})$", candidate)
    if m:
        month = int(m.group(1))
        year = int(m.group(2))
        day = default_day or 1
        day = min(day, calendar.monthrange(year, month)[1])
        return date(year, month, day).strftime("%Y-%m-%d")
    lowered = candidate.lower()
    parts = lowered.split()
    if len(parts) == 2 and parts[0] in MONTH_NAME_MAP and parts[1].isdigit():
        month = MONTH_NAME_MAP[parts[0]]
        year = int(parts[1])
        day = default_day or 1
        day = min(day, calendar.monthrange(year, month)[1])
        return date(year, month, day).strftime("%Y-%m-%d")
    return None


def extract_period_info(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not text:
        return None, None, None
    autopay_segment = None
    autopay_match = re.search(r"((?:\d{2}/\d{2}/\d{4}).{0,40}?){2,}הוראת הקבע", text)
    if autopay_match:
        autopay_segment = autopay_match.group(0)
    if autopay_segment:
        date_tokens = re.findall(r"\d{2}/\d{2}/\d{4}", autopay_segment)
        if len(date_tokens) >= 2:
            parsed_dates = []
            for token in date_tokens:
                normalized = normalize_date_token(token)
                if normalized:
                    parsed_dates.append(datetime.strptime(normalized, "%Y-%m-%d").date())
            if len(parsed_dates) >= 2:
                parsed_dates.sort()
                start_base = parsed_dates[0]
                end_autopay = parsed_dates[-1]
                start_date = start_base.replace(day=1)
                end_date = end_autopay - timedelta(days=1)
                if end_date < start_date:
                    end_date = end_autopay
                start_label = MONTH_LABELS_HE.get(start_date.month, start_date.strftime("%B"))
                end_label = MONTH_LABELS_HE.get(end_date.month, end_date.strftime("%B"))
                label = f"{start_label} - {end_label}"
                return (
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    label,
                )
    range_pattern = re.search(
        r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s*[-–]\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        text,
    )
    if range_pattern:
        start = normalize_date_token(range_pattern.group(1))
        end = normalize_date_token(range_pattern.group(2))
        range_label = f"{start} - {end}" if start and end else None
        return start, end, range_label
    bilingual_pattern = re.search(r"(\d{4})\s+([א-ת]+)\s*[-–]\s*([א-ת]+)", text)
    if bilingual_pattern:
        year = int(bilingual_pattern.group(1))
        month_a = MONTH_NAME_MAP.get(bilingual_pattern.group(2).lower())
        month_b = MONTH_NAME_MAP.get(bilingual_pattern.group(3).lower())
        if month_a and month_b:
            start_date = date(year, month_a, 1)
            end_date = date(year, month_b, calendar.monthrange(year, month_b)[1])
            label = f"{bilingual_pattern.group(3)} - {bilingual_pattern.group(2)}"
            return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), label
    month_year_pattern = re.search(
        r"(?:תקופה|billing|statement|month|חודש)\D*([A-Za-zא-ת]+)\s+(\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if month_year_pattern:
        month_name = month_year_pattern.group(1).lower()
        year = int(month_year_pattern.group(2))
        month = MONTH_NAME_MAP.get(month_name)
        if month:
            start_date = date(year, month, 1)
            end_date = date(year, month, calendar.monthrange(year, month)[1])
            return (
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                f"{start_date:%Y-%m} ({month_year_pattern.group(1)} {year})",
            )
    return None, None, None


def extract_due_date(text: str) -> Optional[str]:
    if not text:
        return None
    patterns = [
        r"(?:Due Date|Payment Due|לתשלום עד|מועד תשלום|תאריך אחרון לתשלום)\D{0,15}([0-9./-]{6,10})",
        r"מועד אחרון[:\s]+([0-9./-]{6,10})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            normalized = normalize_date_token(match.group(1))
            if normalized:
                return normalized
    return None


def extract_reference_numbers(text: str) -> List[str]:
    if not text:
        return []
    patterns = [
        r"(?:PO|P\.O\.|Purchase Order)[\s#:=-]*([A-Z0-9-]{4,})",
        r"מספר\s+(?:הזמנה|לקוח|חוזה|עסקה)[\s#:=-]*([0-9-]{4,})",
        r"(?:Customer ID|Account Number)[\s#:=-]*([A-Z0-9-]{4,})",
    ]
    refs: List[str] = []
    for pattern in patterns:
        refs.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    seen: Dict[str, bool] = {}
    ordered: List[str] = []
    for ref in refs:
        key = ref.strip()
        if not key or key in seen:
            continue
        seen[key] = True
        ordered.append(key)
        if len(ordered) >= 5:
            break
    return ordered


CATEGORY_RULES: List[Tuple[str, float, List[str], List[str]]] = [
    (
        "transportation",
        0.95,
        [
            'דן חברה לתחבורה ציבורית בע"מ',
            "משרד התחבורה והבטיחות בדרכים",
            "תירוביצ הרובחת",
            "תירוביצה הרובחת",
            "התחבורה הציבורית",
            "רב-קו",
            "וק-בר",
            "ravpass",
            "rav-kav",
            "ravkav",
            "rav kav",
        ],
        [
            "תחבורה ציבורית",
            "ravpass",
            "rav-kav",
            "bus",
            "train",
            "light rail",
            "travel card",
        ],
    ),
    (
        "communication",
        1.0,
        [
            "בזק",
            "bezeq",
            "cellcom",
            "partner",
            "פרטנר",
            "hot",
            "yes",
            "סטינג",
            "stingtv",
            "רמי לוי",
            "רמי לוי תקשורת",
            "rami levy",
            "rami-levy",
        ],
        ["תקשורת", "אינטרנט", "internet", "fiber", "broadband"],
    ),
    (
        "utilities",
        0.9,
        ["חשמל", "חברת החשמל", "מים", "תאגיד מים", "ארנונה", "city", "municipality"],
        ["bill", "utility"],
    ),
    (
        "software_saas",
        0.8,
        ["google", "microsoft", "aws", "stripe", "notion", "slack"],
        ["subscription", "license"],
    ),
    ("finance", 0.7, ["visa", "mastercard", "amex", "isracard"], ["כרטיס אשראי"]),
    (
        "services",
        0.6,
        ["קרן-מדריכת הורים ותינוקות", "אופק הפקות"],
        ["שירות", "service", "support"],
    ),
]


def classify_invoice(
    text: str, supplier: Optional[str], is_municipal: bool
) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    if is_municipal:
        return "municipal_tax", 1.0, "municipal_flag"
    text_lower = (text or "").lower()
    supplier_lower = (supplier or "").lower()
    for category, weight, vendor_keys, keyword_hits in CATEGORY_RULES:
        for vendor_key in vendor_keys:
            if vendor_key.lower() in supplier_lower:
                return category, weight, f"vendor:{vendor_key}"
        for keyword in keyword_hits:
            if keyword.lower() in text_lower:
                return category, weight * 0.85, f"keyword:{keyword}"
    return None, None, None


def compute_parse_confidence(record: InvoiceRecord) -> float:
    confidence = 0.4
    if record.invoice_total is not None:
        confidence += 0.25
    if record.invoice_vat is not None:
        confidence += 0.1
    if record.breakdown_sum and record.invoice_total:
        if abs(record.breakdown_sum - record.invoice_total) <= 1.0:
            confidence += 0.15
    if record.period_start or record.period_end:
        confidence += 0.05
    if record.reference_numbers:
        confidence += 0.05
    if record.category:
        confidence += 0.05
    return min(confidence, 0.99)


def file_sha256(path: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def configure_pdfminer_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.ERROR
    for name in (
        "pdfminer",
        "pdfminer.pdfinterp",
        "pdfminer.pdfdocument",
        "pdfminer.converter",
        "pdfminer.pdfpage",
    ):
        logging.getLogger(name).setLevel(level)


def amount_near_markers(
    text: str, patterns: Iterable[str], window: int = 120, prefer: str = "max"
) -> Amount:
    return report_totals.amount_near_markers(text, patterns, window, prefer)


def needs_fallback_text(text: str) -> bool:
    if not text:
        return True
    stripped = text.strip()
    if len(stripped) < 200:
        return True
    hebrew_letters = len(re.findall(r"[א-ת]", stripped))
    glyph_markers = stripped.count("(cid:")
    return hebrew_letters < 15 or glyph_markers > 5


def extract_text_with_pymupdf(path: Path) -> str:
    if not HAVE_PYMUPDF:
        return ""
    try:
        doc = fitz.open(path)
    except Exception:
        return ""
    parts: List[str] = []
    try:
        for page in doc:
            try:
                parts.append(page.get_text("text"))
            except Exception:
                continue
    finally:
        doc.close()
    return "\n".join(parts)


DIRECT_DEBIT_LABELS = report_municipal.DIRECT_DEBIT_LABELS
MUNICIPAL_BREAKDOWN_MARKERS = report_municipal.MUNICIPAL_BREAKDOWN_MARKERS
PARTNER_PERIODIC_MARKERS = report_partner.PARTNER_PERIODIC_MARKERS


def find_municipal_invoice_id(lines: List[str]) -> Tuple[Optional[str], Optional[str]]:
    return report_municipal.find_municipal_invoice_id(lines)


def extract_amount_from_label(page: "fitz.Page", label_tokens: Sequence[str]) -> Amount:
    return report_municipal.extract_amount_from_label(page, label_tokens)


def extract_municipal_breakdown(lines: List[str]) -> Optional[List[float]]:
    return report_municipal.extract_municipal_breakdown(lines)


def normalize_partner_text(text: str) -> str:
    return report_partner.normalize_partner_text(text)


def parse_partner_amount_fragment(fragment: str) -> Optional[float]:
    return report_partner.parse_partner_amount_fragment(fragment)


def extract_partner_amount(normalized: str, marker_pattern: str) -> Optional[float]:
    return report_partner.extract_partner_amount(normalized, marker_pattern)


def extract_partner_totals_from_text(text: str) -> report_partner.PartnerTotalsResult:
    return report_partner.extract_partner_totals_from_text(text)


def extract_partner_totals_from_pdf(path: Path) -> report_partner.PartnerTotalsResult:
    return report_partner.extract_partner_totals_from_pdf(
        path,
        have_pymupdf=HAVE_PYMUPDF,
        open_pdf=lambda target: fitz.open(target),
    )


def split_municipal_multi_invoice(
    path: Path, base_record: InvoiceRecord, debug: bool = False
) -> List[InvoiceRecord]:
    deps = report_splitter.SplitDeps(
        have_pymupdf=HAVE_PYMUPDF,
        open_pdf=lambda target: fitz.open(target),
        extract_lines=extract_lines,
        infer_invoice_date=infer_invoice_date,
        clone_record=lambda rec: replace(cast(InvoiceRecord, rec)),
        compute_parse_confidence=lambda rec: compute_parse_confidence(cast(InvoiceRecord, rec)),
    )
    return cast(
        List[InvoiceRecord],
        report_splitter.split_municipal_multi_invoice(
            path,
            base_record,
            debug=debug,
            deps=deps,
        ),
    )


def extract_lines(text: str) -> List[str]:
    cleaned = text.replace("\r", "\n")
    raw_lines = [ln.strip() for ln in cleaned.splitlines()]
    raw_lines = [ln for ln in raw_lines if ln]

    def is_basic_number(token: str) -> bool:
        return bool(re.fullmatch(r"-?\d+", token))

    merged: List[str] = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        if line == "." and merged and i + 1 < len(raw_lines):
            prev = merged.pop()
            nxt = raw_lines[i + 1]
            if is_basic_number(prev) and is_basic_number(nxt):
                merged.append(f"{nxt}.{prev}")
                i += 2
                continue
            merged.append(prev)
        elif line.endswith(".") and line != "." and line.count(".") == 1:
            body = line[:-1]
            if is_basic_number(body):
                combined = False
                if merged:
                    prev = merged[-1]
                    if is_basic_number(prev):
                        merged[-1] = f"{prev}.{body}"
                        i += 1
                        combined = True
                if combined:
                    continue
                if i + 1 < len(raw_lines):
                    nxt = raw_lines[i + 1]
                    if is_basic_number(nxt):
                        merged.append(f"{nxt}.{body}")
                        i += 2
                        continue
        merged.append(line)
        i += 1

    return [ln for ln in merged if ln]


def search_patterns(patterns: Iterable[str], text: str) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def normalize_invoice_for_value(raw: Optional[str]) -> Optional[str]:
    return report_vendor_strategies.normalize_invoice_for_value(raw)


def infer_invoice_id(lines: List[str], text: str) -> Optional[str]:
    candidates: List[Tuple[int, str]] = []

    if text:
        special_match = re.search(
            r"מס.?['׳]?\s+חשבון\s+תקופתי[:\s-]*([\d-]{6,})",
            text,
            flags=re.MULTILINE,
        )
        if special_match:
            cleaned = re.sub(r"\D", "", special_match.group(1))
            if cleaned:
                return cleaned
        normalized_id_text = " ".join(text.split())
        alt_match = re.search(r"(\d{3,})\s+קבלה\s+מס\s+חשבונית", normalized_id_text)
        if alt_match:
            cleaned = re.sub(r"\D", "", alt_match.group(1))
            if cleaned:
                return cleaned
        period_match = re.search(
            r"([\d-]{6,})[\s\S]{0,80}?[:]?יתפוקת",
            text,
            flags=re.MULTILINE,
        )
        if period_match:
            cleaned = re.sub(r"\D", "", period_match.group(1))
            if cleaned:
                return cleaned

    def add_candidate(value: Optional[str], priority: int) -> None:
        val = (value or "").strip()
        if not val:
            return
        cleaned = re.sub(r"[^\d]", "", val)
        candidates.append((priority, cleaned or val))

    pattern_defs = [
        (r"חשבונית\s+מס\s+קבלה\s*(\d+)", 0),
        (r"חשבונית(?:\s+מס)?(?:\s+קבלה)?\s*(?:מספר|No\.?)\s*[:\-]?\s*(\d+)", 0),
        (r"(\d{4,})\s*רפסמ\s*תינובשח", 0),
        (r"(\d{4,})\s*רפסמ\s*קיתב\s*מ\"עמ", 1),
        (r"(\d{4,})\s+רפסמ", 2),
        (r"מספר\s+(\d{4,})", 2),
        (r"מס.?['׳]?\s*מסלקה/שובר/ספח[:\s]+(\d{4,})", 0),
        (r"מסלקה/שובר/ספח[:\s]+(\d{4,})", 1),
    ]
    for pattern, priority in pattern_defs:
        for match in re.finditer(pattern, text):
            add_candidate(match.group(1), priority)

    if not candidates:
        for idx, line in enumerate(lines):
            if "רפסמ" in line:
                digits = re.findall(r"\d[\d/-]*", line)
                for val in digits:
                    add_candidate(val, 3)
                if digits:
                    break
                if idx > 0:
                    prev = re.findall(r"\d[\d/-]*", lines[idx - 1])
                    for val in prev:
                        add_candidate(val, 3)
                    break
    if not candidates:
        for line in lines[:60]:
            for token in re.findall(r"\b\d{8,12}\b", line):
                add_candidate(token, 5)
    if not candidates and text:
        for token in re.findall(r"\b\d{8,12}\b", text):
            add_candidate(token, 6)

    if candidates:
        candidates.sort(key=lambda item: (item[0], -len(item[1]), item[1]))
        return candidates[0][1]
    return None


def infer_invoice_date(text: str) -> Optional[str]:
    patterns = [
        r"(\d{2}/\d{2}/\d{4})\s*:ךיראת",
        r"תאריך\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
        r"Date\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
        r"תאריך\s*הדפסה\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
    ]
    value = search_patterns(patterns, text)
    if value:
        return value
    match = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    if match:
        return match.group(1)
    return None


def detect_known_vendor(text: Optional[str]) -> Optional[str]:
    return report_vendor_strategies.detect_known_vendor(text)


def has_public_transport_marker(text: Optional[str]) -> bool:
    return report_vendor_strategies.has_public_transport_marker(text)


def looks_like_petah_tikva_municipality(text: Optional[str]) -> bool:
    return report_vendor_strategies.looks_like_petah_tikva_municipality(text)


def infer_invoice_from(lines: List[str], text: Optional[str] = None) -> Optional[str]:
    return report_vendor_strategies.infer_invoice_from(lines, text)


def numeric_candidates(line: str) -> List[tuple[str, bool]]:
    return report_totals.numeric_candidates(line)


def numeric_values_near_marker(lines: List[str], marker: str, window: int = 4) -> List[float]:
    return report_totals.numeric_values_near_marker(lines, marker, window)


def normalize_marker_text(line: str) -> str:
    return report_totals.normalize_marker_text(line)


def is_total_with_vat_line(line: str) -> bool:
    return report_totals.is_total_with_vat_line(line)


def is_vat_percent_line(line: str) -> bool:
    return report_totals.is_vat_percent_line(line)


def amount_from_line_end(line: str) -> Amount:
    return report_totals.amount_from_line_end(line)


def repeated_currency_total(currency_tokens: List[str]) -> Amount:
    return report_totals.repeated_currency_total(currency_tokens)


def extract_total_from_total_with_vat_lines(lines: List[str], currency_tokens: List[str]) -> Amount:
    return report_totals.extract_total_from_total_with_vat_lines(lines, currency_tokens)


def extract_vat_from_percent_lines(
    lines: List[str],
    currency_tokens: List[str],
    *,
    total: Amount,
    explicit_vat_rate: Optional[float],
) -> Amount:
    return report_totals.extract_vat_from_percent_lines(
        lines,
        currency_tokens,
        total=total,
        explicit_vat_rate=explicit_vat_rate,
    )


def sum_numeric_block(
    lines: List[str],
    start_markers: Iterable[str],
    end_markers: Iterable[str],
) -> Tuple[Optional[float], List[float]]:
    return report_totals.sum_numeric_block(lines, start_markers, end_markers)


def extract_keren_invoice_for(text: Optional[str]) -> Optional[str]:
    return report_vendor_strategies.extract_keren_invoice_for(text)


def extract_partner_invoice_for(lines: List[str], raw_text: Optional[str] = None) -> Optional[str]:
    return report_vendor_strategies.extract_partner_invoice_for(lines, raw_text)


def extract_ofek_invoice_for(text: Optional[str]) -> Optional[str]:
    return report_vendor_strategies.extract_ofek_invoice_for(text)


def extract_stingtv_invoice_for(text: Optional[str]) -> Optional[str]:
    return report_vendor_strategies.extract_stingtv_invoice_for(text)


def extract_stingtv_breakdown(text: Optional[str]) -> List[float]:
    return report_vendor_strategies.extract_stingtv_breakdown(text)


def extract_just_simple_invoice_for(
    lines: List[str], raw_text: Optional[str] = None
) -> Optional[str]:
    return report_vendor_strategies.extract_just_simple_invoice_for(lines, raw_text)


def infer_invoice_for(lines: List[str], text: Optional[str] = None) -> Optional[str]:
    return report_vendor_strategies.infer_invoice_for(lines, text)


def find_amount_before_marker(
    lines: List[str], marker: str, *, prefer_inline: bool = False
) -> Amount:
    return report_totals.find_amount_before_marker(lines, marker, prefer_inline=prefer_inline)


def vat_rate_estimate(total: Optional[float], vat: Optional[float]) -> Optional[float]:
    return report_totals.vat_rate_estimate(total, vat)


def extract_vat_rate_from_text(text: Optional[str]) -> Optional[float]:
    return report_totals.extract_vat_rate_from_text(text)


def infer_totals(
    lines: List[str],
    text: str,
    *,
    debug: bool = False,
    label: str = "",
    pdfminer_lines: Optional[List[str]] = None,
) -> report_totals.TotalsResult:
    return report_totals.infer_totals(
        lines,
        text,
        debug=debug,
        label=label,
        pdfminer_lines=pdfminer_lines,
    )


def parse_invoice(path: Path, debug: bool = False) -> InvoiceRecord:
    deps = report_parser.ParserDeps(
        extract_text=extract_text,
        needs_fallback_text=needs_fallback_text,
        extract_text_with_pymupdf=extract_text_with_pymupdf,
        extract_lines=extract_lines,
        infer_invoice_id=infer_invoice_id,
        infer_invoice_date=infer_invoice_date,
        infer_invoice_from=infer_invoice_from,
        infer_invoice_for=infer_invoice_for,
        infer_totals=infer_totals,
        extract_partner_totals_from_pdf=extract_partner_totals_from_pdf,
        extract_period_info=extract_period_info,
        extract_due_date=extract_due_date,
        extract_reference_numbers=extract_reference_numbers,
        classify_invoice=classify_invoice,
        file_sha256=file_sha256,
        compute_parse_confidence=lambda rec: compute_parse_confidence(cast(InvoiceRecord, rec)),
        record_factory=lambda source_file: InvoiceRecord(source_file=source_file),
        have_pymupdf=HAVE_PYMUPDF,
    )
    return cast(InvoiceRecord, report_parser.parse_invoice(path, debug=debug, deps=deps))


def parse_invoices(path: Path, debug: bool = False) -> List[InvoiceRecord]:
    return cast(
        List[InvoiceRecord],
        report_pipeline.parse_path(
            path,
            debug=debug,
            parse_invoice_fn=lambda target, dbg: parse_invoice(target, debug=dbg),
            split_municipal_multi_invoice_fn=lambda target,
            record,
            dbg: split_municipal_multi_invoice(
                target,
                record,
                debug=dbg,
            ),
        ),
    )


def generate_report(
    input_dir: Path,
    *,
    selected_files: Optional[List[str]] = None,
    debug: bool = False,
) -> List[InvoiceRecord]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    records: List[InvoiceRecord] = []
    candidates: List[Path]
    if selected_files:
        candidates = []
        for name in selected_files:
            candidate = Path(name)
            if not candidate.is_absolute():
                candidate = input_dir / candidate
            candidates.append(candidate)
    else:
        candidates = sorted(input_dir.glob("*.pdf"))

    for path in candidates:
        if not path.exists():
            if debug:
                print(f"[debug] Skip missing file: {path}")
            continue
        records.extend(parse_invoices(path, debug=debug))
    return records


def write_json(records: List[InvoiceRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump([asdict(rec) for rec in records], fh, ensure_ascii=False, indent=2)


def write_csv(records: List[InvoiceRecord], output_path: Path) -> None:
    fields = [
        "source_file",
        "invoice_id",
        "invoice_date",
        "invoice_from",
        "invoice_for",
        "base_before_vat",
        "invoice_vat",
        "invoice_total",
        "currency",
        "breakdown_sum",
        "breakdown_values",
        "notes",
        "vat_rate",
        "period_start",
        "period_end",
        "period_label",
        "due_date",
        "category",
        "category_confidence",
        "category_rule",
        "reference_numbers",
        "data_source",
        "parse_confidence",
        "municipal",
        "duplicate_hash",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(fields)
        for record in records:
            writer.writerow(record.to_csv_row(fields))


def write_summary_csv(
    totals: Dict[str, Dict[str, Optional[float] | int]], output_path: Path
) -> None:
    def fmt(value: Optional[float] | int) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    fields = [
        "metric",
        "sum",
        "abs_sum",
        "count",
        "missing",
        "zero",
        "negative",
        "positive",
        "min",
        "max",
        "avg",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(fields)
        records_info = totals.get("records", {})
        writer.writerow(
            [
                "records",
                "",
                "",
                fmt(records_info.get("count")),
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
        for metric in ("invoice_vat", "invoice_total"):
            info = totals.get(metric, {})
            writer.writerow(
                [
                    metric,
                    fmt(info.get("sum")),
                    fmt(info.get("abs_sum")),
                    fmt(info.get("count")),
                    fmt(info.get("missing")),
                    fmt(info.get("zero")),
                    fmt(info.get("negative")),
                    fmt(info.get("positive")),
                    fmt(info.get("min")),
                    fmt(info.get("max")),
                    fmt(info.get("avg")),
                ]
            )


def _resolve_pdf_font_file() -> Optional[str]:
    candidates = [
        os.environ.get("INVOICE_REPORT_FONT"),
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Hebrew.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None


def _format_pdf_value(field: str, value: object) -> str:
    if value is None:
        return ""
    if field in {"base_before_vat", "invoice_vat", "invoice_total"}:
        if isinstance(value, (int, float)):
            return f"{float(value):,.2f}"
        return ""
    compact = " ".join(str(value).split())
    if len(compact) > 120:
        return compact[:117] + "..."
    return compact


def _pdf_color_to_css(color: Tuple[float, float, float]) -> str:
    red = max(0, min(255, round(color[0] * 255)))
    green = max(0, min(255, round(color[1] * 255)))
    blue = max(0, min(255, round(color[2] * 255)))
    return f"rgb({red}, {green}, {blue})"


def _render_pdf_cell_text(
    page: "fitz.Page",
    rect: "fitz.Rect",
    text: str,
    *,
    align: int,
    font_name: str,
    fontsize: float,
    color: Tuple[float, float, float],
) -> None:
    align_map = {0: "left", 1: "center", 2: "right"}
    text_align = align_map.get(align, "left")
    css = (
        f"* {{ font-family: {font_name}; font-size: {fontsize}pt; color: {_pdf_color_to_css(color)}; }}"
        f" div {{ unicode-bidi: plaintext; text-align: {text_align};"
        " white-space: nowrap; }"
    )
    escaped_text = html.escape(text)
    page.insert_htmlbox(rect, f'<div dir="auto">{escaped_text}</div>', css=css)


def _sum_field(records: Sequence[InvoiceRecord], field: str) -> Optional[float]:
    total = 0.0
    has_value = False
    for record in records:
        value = getattr(record, field, None)
        if value is None:
            continue
        total += value
        has_value = True
    return round(total, 2) if has_value else None


def _vendor_display_name(record: InvoiceRecord) -> str:
    name = " ".join((record.invoice_from or "").split()).strip()
    return name or "Unknown Vendor"


def _invoice_date_sort_key(value: Optional[str]) -> str:
    if not value:
        return "9999-12-31"
    try:
        return datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return value


def _build_pdf_rows_with_vendor_subtotals(
    records: Sequence[InvoiceRecord],
    *,
    include_vendor_subtotals: bool = True,
    skip_single_vendor_subtotals: bool = False,
) -> List[Tuple[str, Dict[str, object]]]:
    sorted_records = sorted(
        records,
        key=lambda rec: (
            _vendor_display_name(rec).casefold(),
            _invoice_date_sort_key(rec.invoice_date),
            rec.invoice_id or "",
            rec.source_file,
        ),
    )

    rows: List[Tuple[str, Dict[str, object]]] = []
    current_vendor: Optional[str] = None
    vendor_records: List[InvoiceRecord] = []

    def flush_vendor_group() -> None:
        nonlocal vendor_records
        if not vendor_records:
            return
        vendor_name = _vendor_display_name(vendor_records[0])
        for rec in vendor_records:
            rows.append(("detail", asdict(rec)))

        should_add_subtotal = include_vendor_subtotals and (
            not skip_single_vendor_subtotals or len(vendor_records) > 1
        )
        if should_add_subtotal:
            rows.append(
                (
                    "vendor_subtotal",
                    {
                        "invoice_from": vendor_name,
                        "invoice_for": "Vendor Subtotal",
                        "base_before_vat": _sum_field(vendor_records, "base_before_vat"),
                        "invoice_vat": _sum_field(vendor_records, "invoice_vat"),
                        "invoice_total": _sum_field(vendor_records, "invoice_total"),
                    },
                )
            )
        vendor_records = []

    for record in sorted_records:
        vendor_name = _vendor_display_name(record)
        if current_vendor is None:
            current_vendor = vendor_name
        if vendor_name != current_vendor:
            flush_vendor_group()
            current_vendor = vendor_name
        vendor_records.append(record)
    flush_vendor_group()

    rows.append(
        (
            "grand_total",
            {
                "invoice_for": "Grand Total",
                "base_before_vat": _sum_field(records, "base_before_vat"),
                "invoice_vat": _sum_field(records, "invoice_vat"),
                "invoice_total": _sum_field(records, "invoice_total"),
            },
        )
    )
    return rows


def write_pdf_report(
    records: Sequence[InvoiceRecord],
    output_path: Path,
    *,
    include_vendor_subtotals: bool = True,
    skip_single_vendor_subtotals: bool = False,
) -> None:
    if not HAVE_PYMUPDF:
        raise SystemExit(
            "Missing dependency: pymupdf is required for PDF report generation. "
            "Install it with `pip install pymupdf`."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    font_file = _resolve_pdf_font_file()
    page_width = 842.0
    page_height = 595.0
    margin = 24.0
    header_h = 24.0
    row_h = 22.0
    table_width = page_width - (margin * 2)
    table_bottom_limit = page_height - margin
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    header_fill = (0.12, 0.28, 0.45)
    header_text_color = (1.0, 1.0, 1.0)
    zebra_odd = (1.0, 1.0, 1.0)
    zebra_even = (0.95, 0.97, 0.99)
    vendor_subtotal_fill = (0.90, 0.94, 0.98)
    summary_fill = (0.85, 0.91, 0.97)
    border_color = (0.73, 0.76, 0.80)
    body_text_color = (0.13, 0.13, 0.13)

    page = doc.new_page(width=page_width, height=page_height)
    body_font_name = "helv"
    if font_file:
        body_font_name = "invoice_body"
        page.insert_font(fontname=body_font_name, fontfile=font_file)

    def draw_page_header(active_page: fitz.Page) -> float:
        if font_file:
            active_page.insert_font(fontname=body_font_name, fontfile=font_file)
        active_page.insert_text(
            fitz.Point(margin, margin),
            "Invoice Summary Report",
            fontsize=14,
            fontname="helv",
            color=(0.09, 0.19, 0.30),
        )
        active_page.insert_text(
            fitz.Point(margin, margin + 14),
            f"Generated: {timestamp}",
            fontsize=8,
            fontname="helv",
            color=(0.40, 0.44, 0.50),
        )
        y = margin + 22
        x = margin
        for _field, header_label, width_ratio, _align in PDF_REPORT_COLUMNS:
            cell_w = table_width * width_ratio
            rect = fitz.Rect(x, y, x + cell_w, y + header_h)
            active_page.draw_rect(rect, color=border_color, fill=header_fill, width=0.6)
            active_page.insert_textbox(
                fitz.Rect(rect.x0 + 4, rect.y0 + 4, rect.x1 - 4, rect.y1 - 3),
                header_label,
                fontsize=8.2,
                fontname="helv",
                color=header_text_color,
                align=1,
            )
            x += cell_w
        return y + header_h

    def draw_row(
        active_page: fitz.Page,
        y: float,
        row_data: Dict[str, object],
        *,
        fill_color: Tuple[float, float, float],
        is_summary: bool = False,
    ) -> None:
        x = margin
        for field, _header, width_ratio, align in PDF_REPORT_COLUMNS:
            cell_w = table_width * width_ratio
            rect = fitz.Rect(x, y, x + cell_w, y + row_h)
            active_page.draw_rect(rect, color=border_color, fill=fill_color, width=0.5)
            text = _format_pdf_value(field, row_data.get(field))
            _render_pdf_cell_text(
                active_page,
                fitz.Rect(rect.x0 + 4, rect.y0 + 4, rect.x1 - 4, rect.y1 - 3),
                text,
                align=align,
                font_name=body_font_name,
                fontsize=8.2 if is_summary else 8.0,
                color=body_text_color,
            )
            x += cell_w

    rows = _build_pdf_rows_with_vendor_subtotals(
        records,
        include_vendor_subtotals=include_vendor_subtotals,
        skip_single_vendor_subtotals=skip_single_vendor_subtotals,
    )

    current_y = draw_page_header(page)
    detail_idx = 0
    for row_type, row_data in rows:
        if current_y + row_h > table_bottom_limit:
            page = doc.new_page(width=page_width, height=page_height)
            current_y = draw_page_header(page)
        if row_type == "detail":
            fill_color = zebra_odd if detail_idx % 2 == 0 else zebra_even
            draw_row(page, current_y, row_data, fill_color=fill_color)
            detail_idx += 1
        elif row_type == "vendor_subtotal":
            draw_row(page, current_y, row_data, fill_color=vendor_subtotal_fill, is_summary=True)
        else:
            draw_row(page, current_y, row_data, fill_color=summary_fill, is_summary=True)
        current_y += row_h

    doc.save(output_path)
    doc.close()


def compute_report_totals(
    records: Sequence[InvoiceRecord],
) -> Dict[str, Dict[str, Optional[float] | int]]:
    def stats_for(field: str) -> Dict[str, Optional[float]]:
        total = 0.0
        abs_total = 0.0
        count = 0
        missing = 0
        zero = 0
        negative = 0
        positive = 0
        min_val: Optional[float] = None
        max_val: Optional[float] = None
        for record in records:
            value = getattr(record, field, None)
            if value is None:
                missing += 1
                continue
            if value == 0:
                zero += 1
                continue
            count += 1
            total += value
            abs_total += abs(value)
            if value < 0:
                negative += 1
            else:
                positive += 1
            if min_val is None or value < min_val:
                min_val = value
            if max_val is None or value > max_val:
                max_val = value
        avg = round(total / count, 2) if count else None
        return {
            "sum": round(total, 2),
            "abs_sum": round(abs_total, 2),
            "count": count,
            "missing": missing,
            "zero": zero,
            "negative": negative,
            "positive": positive,
            "min": min_val,
            "max": max_val,
            "avg": avg,
        }

    return {
        "records": {"count": len(records)},
        "invoice_vat": stats_for("invoice_vat"),
        "invoice_total": stats_for("invoice_total"),
    }


def print_report_totals(totals: Dict[str, Dict[str, Optional[float]]]) -> None:
    def fmt(val: Optional[float]) -> str:
        if val is None:
            return "n/a"
        if isinstance(val, float):
            return f"{val:.2f}"
        return str(val)

    print("Totals (non-zero values):")
    for field in ("invoice_vat", "invoice_total"):
        info = totals.get(field, {})
        print(
            f"  {field}: sum={fmt(info.get('sum'))} "
            f"(count={int(info.get('count') or 0)}, "
            f"missing={int(info.get('missing') or 0)}, "
            f"zero={int(info.get('zero') or 0)}, "
            f"negative={int(info.get('negative') or 0)}, "
            f"avg={fmt(info.get('avg'))}, "
            f"min={fmt(info.get('min'))}, "
            f"max={fmt(info.get('max'))}, "
            f"abs_sum={fmt(info.get('abs_sum'))})"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a report from downloaded invoice PDFs.")
    parser.add_argument(
        "--input-dir",
        default="invoices_outlook",
        help="Directory containing invoice PDF files (default: invoices_outlook)",
    )
    parser.add_argument(
        "--json-output",
        default="invoice_report.json",
        help="Path for JSON report (default: invoice_report.json)",
    )
    parser.add_argument(
        "--csv-output",
        default="invoice_report.csv",
        help="Path for CSV report (default: invoice_report.csv)",
    )
    parser.add_argument(
        "--summary-csv-output",
        default=None,
        help="Path for summary CSV totals (default: <csv-output>.summary.csv)",
    )
    parser.add_argument(
        "--pdf-output",
        default=None,
        help="Path for PDF report (default: <csv-output>.pdf)",
    )
    parser.add_argument(
        "--pdf-vendor-subtotals",
        dest="pdf_vendor_subtotals",
        action="store_true",
        default=True,
        help="Include per-vendor subtotal rows in the PDF report (default: enabled).",
    )
    parser.add_argument(
        "--no-pdf-vendor-subtotals",
        dest="pdf_vendor_subtotals",
        action="store_false",
        help="Disable per-vendor subtotal rows in the PDF report.",
    )
    parser.add_argument(
        "--pdf-skip-single-vendor-subtotals",
        action="store_true",
        default=False,
        help="When vendor subtotals are enabled, skip subtotal rows for vendors with one invoice.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print detailed parsing diagnostics per invoice.",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        default=None,
        help="Specific invoice file names to process (relative to input dir).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_pdfminer_logging(args.debug)
    input_dir = Path(args.input_dir)
    selected = args.files if args.files else None
    records = generate_report(input_dir, selected_files=selected, debug=args.debug)
    write_json(records, Path(args.json_output))
    csv_path = Path(args.csv_output)
    write_csv(records, csv_path)
    print(
        f"Generated {len(records)} records → {args.json_output}, {args.csv_output}",
    )
    totals = compute_report_totals(records)
    print_report_totals(totals)
    summary_path = (
        Path(args.summary_csv_output)
        if args.summary_csv_output
        else csv_path.with_suffix(".summary.csv")
    )
    write_summary_csv(totals, summary_path)
    print(f"Summary totals → {summary_path}")
    if HAVE_PYMUPDF:
        pdf_path = Path(args.pdf_output) if args.pdf_output else csv_path.with_suffix(".pdf")
        write_pdf_report(
            records,
            pdf_path,
            include_vendor_subtotals=args.pdf_vendor_subtotals,
            skip_single_vendor_subtotals=args.pdf_skip_single_vendor_subtotals,
        )
        print(f"PDF report → {pdf_path}")
    else:
        print("PDF report skipped (pymupdf is not installed)")


if __name__ == "__main__":  # pragma: no cover
    main()
