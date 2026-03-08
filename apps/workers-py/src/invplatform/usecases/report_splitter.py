from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

from invplatform.usecases import report_municipal


class InvoiceRecordLike(Protocol):
    municipal: Optional[bool]
    notes: Optional[str]
    invoice_id: Optional[str]
    invoice_for: Optional[str]
    invoice_date: Optional[str]
    invoice_total: Optional[float]
    breakdown_values: Optional[List[float]]
    breakdown_sum: Optional[float]
    invoice_vat: Optional[float]
    data_source: Optional[str]
    parse_confidence: Optional[float]


@dataclass(frozen=True)
class SplitDeps:
    have_pymupdf: bool
    open_pdf: Callable[[Path], Any]
    extract_lines: Callable[[str], List[str]]
    infer_invoice_date: Callable[[str], Optional[str]]
    clone_record: Callable[[InvoiceRecordLike], InvoiceRecordLike]
    compute_parse_confidence: Callable[[InvoiceRecordLike], float]


def split_municipal_multi_invoice(
    path: Path,
    base_record: InvoiceRecordLike,
    *,
    debug: bool = False,
    deps: SplitDeps,
) -> List[InvoiceRecordLike]:
    if not deps.have_pymupdf or not base_record.municipal:
        return [base_record]
    if base_record.notes == "extract_text_failed":
        return [base_record]
    try:
        doc = deps.open_pdf(path)
    except Exception:
        return [base_record]
    entries: List[Dict[str, object]] = []
    try:
        for page in doc:
            text = page.get_text("text")
            if not text:
                continue
            if not any(label in text for label in report_municipal.DIRECT_DEBIT_LABELS):
                continue
            lines = deps.extract_lines(text)
            invoice_id, invoice_for = report_municipal.find_municipal_invoice_id(lines)
            if not invoice_id:
                continue
            total = report_municipal.extract_amount_from_label(page, ["יגבה"])
            if total is None:
                total = report_municipal.extract_amount_from_label(page, ["לתשלום"])
            breakdown_values = report_municipal.extract_municipal_breakdown(lines)
            breakdown_sum = round(sum(breakdown_values), 2) if breakdown_values else None
            if total is None and breakdown_sum is None:
                continue
            entries.append(
                {
                    "invoice_id": invoice_id,
                    "invoice_for": invoice_for,
                    "invoice_date": deps.infer_invoice_date(text),
                    "invoice_total": total or breakdown_sum,
                    "breakdown_values": breakdown_values,
                    "breakdown_sum": breakdown_sum,
                }
            )
    finally:
        doc.close()
    if len(entries) < 2:
        return [base_record]
    seen: set[str] = set()
    records: List[InvoiceRecordLike] = []
    for entry in entries:
        entry_invoice_id = entry["invoice_id"]
        if not isinstance(entry_invoice_id, str) or entry_invoice_id in seen:
            continue
        seen.add(entry_invoice_id)
        record = deps.clone_record(base_record)
        record.invoice_id = entry_invoice_id
        entry_invoice_for = entry.get("invoice_for")
        record.invoice_for = (
            entry_invoice_for if isinstance(entry_invoice_for, str) else base_record.invoice_for
        )
        entry_invoice_date = entry.get("invoice_date")
        record.invoice_date = (
            entry_invoice_date if isinstance(entry_invoice_date, str) else base_record.invoice_date
        )
        entry_invoice_total = entry.get("invoice_total")
        record.invoice_total = (
            float(entry_invoice_total) if isinstance(entry_invoice_total, (int, float)) else None
        )
        entry_breakdown_values = entry.get("breakdown_values")
        record.breakdown_values = (
            entry_breakdown_values if isinstance(entry_breakdown_values, list) else None
        )
        entry_breakdown_sum = entry.get("breakdown_sum")
        record.breakdown_sum = (
            float(entry_breakdown_sum) if isinstance(entry_breakdown_sum, (int, float)) else None
        )
        record.invoice_vat = 0.0
        record.data_source = "pymupdf"
        record.parse_confidence = deps.compute_parse_confidence(record)
        if (
            isinstance(entry_breakdown_sum, (int, float))
            and isinstance(entry_invoice_total, (int, float))
            and abs(float(entry_breakdown_sum) - float(entry_invoice_total)) > 1.0
        ):
            record.notes = (record.notes + "; " if record.notes else "") + (
                "Total differs from breakdown sum"
            )
        records.append(record)
    if len(records) < 2:
        return [base_record]
    if debug:
        print(f"[debug][{path.name}] municipal split into {len(records)} records")
    return records
