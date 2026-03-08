from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Protocol, Tuple

from invplatform.usecases.report_partner import PartnerTotalsResult
from invplatform.usecases.report_totals import TotalsResult


class InvoiceRecordLike(Protocol):
    notes: Optional[str]
    invoice_id: Optional[str]
    invoice_date: Optional[str]
    invoice_from: Optional[str]
    invoice_for: Optional[str]
    invoice_total: Optional[float]
    invoice_vat: Optional[float]
    breakdown_sum: Optional[float]
    breakdown_values: Optional[List[float]]
    base_before_vat: Optional[float]
    vat_rate: Optional[float]
    municipal: Optional[bool]
    period_start: Optional[str]
    period_end: Optional[str]
    period_label: Optional[str]
    due_date: Optional[str]
    reference_numbers: Optional[List[str]]
    category: Optional[str]
    category_confidence: Optional[float]
    category_rule: Optional[str]
    data_source: Optional[str]
    duplicate_hash: Optional[str]
    parse_confidence: Optional[float]


@dataclass(frozen=True)
class ParserDeps:
    extract_text: Callable[[Path], str]
    needs_fallback_text: Callable[[str], bool]
    extract_text_with_pymupdf: Callable[[Path], str]
    extract_lines: Callable[[str], List[str]]
    infer_invoice_id: Callable[[List[str], str], Optional[str]]
    infer_invoice_date: Callable[[str], Optional[str]]
    infer_invoice_from: Callable[[List[str], Optional[str]], Optional[str]]
    infer_invoice_for: Callable[[List[str], Optional[str]], Optional[str]]
    infer_totals: Callable[..., TotalsResult]
    extract_partner_totals_from_pdf: Callable[[Path], PartnerTotalsResult]
    extract_period_info: Callable[[str], Tuple[Optional[str], Optional[str], Optional[str]]]
    extract_due_date: Callable[[str], Optional[str]]
    extract_reference_numbers: Callable[[str], List[str]]
    classify_invoice: Callable[
        [str, Optional[str], bool], Tuple[Optional[str], Optional[float], Optional[str]]
    ]
    file_sha256: Callable[[Path], Optional[str]]
    compute_parse_confidence: Callable[[InvoiceRecordLike], float]
    record_factory: Callable[[str], InvoiceRecordLike]
    have_pymupdf: bool


def parse_invoice(path: Path, *, debug: bool = False, deps: ParserDeps) -> InvoiceRecordLike:
    try:
        text_pdfminer = deps.extract_text(path)
    except Exception:  # pragma: no cover - defensive
        text_pdfminer = ""

    if not text_pdfminer:
        record = deps.record_factory(path.name)
        record.notes = "extract_text_failed"
        return record

    text = text_pdfminer
    used_fallback = False
    fallback_text = ""
    if deps.needs_fallback_text(text_pdfminer):
        fallback_text = deps.extract_text_with_pymupdf(path)
        if fallback_text:
            text = fallback_text
            used_fallback = True

    if fallback_text:
        pymupdf_text_cache: Optional[str] = fallback_text
        pymupdf_lines_cache: Optional[List[str]] = deps.extract_lines(fallback_text)
    else:
        pymupdf_text_cache = None
        pymupdf_lines_cache = None

    def ensure_pymupdf_data() -> None:
        nonlocal pymupdf_text_cache, pymupdf_lines_cache
        if pymupdf_text_cache is not None:
            return
        if not deps.have_pymupdf:
            pymupdf_text_cache = ""
            pymupdf_lines_cache = []
            return
        extra = deps.extract_text_with_pymupdf(path)
        pymupdf_text_cache = extra or ""
        pymupdf_lines_cache = deps.extract_lines(pymupdf_text_cache) if pymupdf_text_cache else []

    def get_pymupdf_text() -> str:
        ensure_pymupdf_data()
        return pymupdf_text_cache or ""

    def get_pymupdf_lines() -> List[str]:
        ensure_pymupdf_data()
        return pymupdf_lines_cache or []

    lines = deps.extract_lines(text)
    if debug:
        print(f"\n[debug][{path.name}] === pdfminer text preview ===")
        preview_pdfminer = "\n".join(text_pdfminer.replace("\r", "\n").splitlines()[:40])
        print(preview_pdfminer or "(no text extracted)")
        if fallback_text:
            print(f"\n[debug][{path.name}] === PyMuPDF text preview ===")
            preview_pymupdf = "\n".join(fallback_text.replace("\r", "\n").splitlines()[:40])
            print(preview_pymupdf or "(no fallback text)")
        print(f"\n[debug][{path.name}] === normalized lines preview ===")
        preview = "\n".join(lines[:40])
        print(preview or "(no text extracted)")

    record = deps.record_factory(path.name)
    record.invoice_id = deps.infer_invoice_id(lines, text)
    record.invoice_date = deps.infer_invoice_date(text)
    invoice_from = deps.infer_invoice_from(lines, text)
    if not invoice_from or invoice_from.startswith(":"):
        extra_text = get_pymupdf_text()
        extra_lines = get_pymupdf_lines()
        if extra_text and extra_lines:
            alt_from = deps.infer_invoice_from(extra_lines, extra_text)
            if alt_from:
                invoice_from = alt_from
    if invoice_from and len(invoice_from) > 120:
        invoice_from = invoice_from[:117] + "..."
    record.invoice_from = invoice_from

    invoice_for = deps.infer_invoice_for(lines, text)
    if not invoice_for:
        extra_text = get_pymupdf_text()
        extra_lines = get_pymupdf_lines()
        if extra_text and extra_lines:
            invoice_for = deps.infer_invoice_for(extra_lines, extra_text)
    record.invoice_for = invoice_for

    lines_pdfminer = deps.extract_lines(text_pdfminer)
    totals = deps.infer_totals(
        lines,
        text,
        debug=debug,
        label=path.name,
        pdfminer_lines=lines_pdfminer,
    )
    if any(marker in text for marker in ("פרטנר", "partner", "Partner")):
        partner_totals = deps.extract_partner_totals_from_pdf(path)
        if partner_totals:
            partner_total = partner_totals.get("invoice_total")
            if partner_total is not None:
                totals["invoice_total"] = partner_total
            partner_vat = partner_totals.get("invoice_vat")
            if partner_vat is not None:
                totals["invoice_vat"] = partner_vat
            partner_base = partner_totals.get("base_before_vat")
            if partner_base is not None:
                totals["base_before_vat"] = partner_base
            if debug:
                print(
                    f"[debug][{path.name}] partner periodic totals override "
                    f"total={totals.get('invoice_total')} vat={totals.get('invoice_vat')} "
                    f"base={totals.get('base_before_vat')}"
                )

    record.invoice_total = totals.get("invoice_total")
    record.invoice_vat = totals.get("invoice_vat")
    record.breakdown_sum = totals.get("breakdown_sum")
    breakdown_values = totals.get("breakdown_values")
    if breakdown_values:
        record.breakdown_values = breakdown_values
    record.base_before_vat = totals.get("base_before_vat")
    record.vat_rate = totals.get("vat_rate")
    record.municipal = totals.get("municipal")
    if (
        record.breakdown_sum is not None
        and record.invoice_total is not None
        and abs(record.breakdown_sum - record.invoice_total) > 1.0
    ):
        if record.notes:
            record.notes += "; "
        else:
            record.notes = ""
        record.notes += "Total differs from breakdown sum"

    if totals.get("municipal"):
        if not record.invoice_from:
            if "פתח תק" in text or "הווקת חתפ" in text:
                record.invoice_from = "עיריית פתח תקווה"
            else:
                record.invoice_from = "רשות מקומית"
        if record.invoice_vat is None:
            record.invoice_vat = 0.0

    period_start, period_end, period_label = deps.extract_period_info(text)
    record.period_start = period_start
    record.period_end = period_end
    record.period_label = period_label
    record.due_date = deps.extract_due_date(text)
    references = deps.extract_reference_numbers(text)
    if references:
        record.reference_numbers = references
    category, category_confidence, category_rule = deps.classify_invoice(
        text, record.invoice_from, bool(record.municipal)
    )
    record.category = category
    record.category_confidence = category_confidence
    record.category_rule = category_rule
    record.data_source = "pymupdf" if used_fallback else "pdfminer"
    record.duplicate_hash = deps.file_sha256(path)
    record.parse_confidence = deps.compute_parse_confidence(record)

    if debug:
        if used_fallback:
            print(f"[debug][{path.name}] used PyMuPDF fallback for text extraction")
        print(
            f"[debug][{path.name}] summary: total={record.invoice_total} "
            f"vat={record.invoice_vat} id={record.invoice_id} from={record.invoice_from}"
        )
    return record
