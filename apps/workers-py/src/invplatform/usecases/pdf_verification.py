from __future__ import annotations

from typing import Callable, Dict, Iterable, Tuple

PdfKeywordStats = Callable[[str], Dict]


def decide_pdf_relevance_graph(
    path: str,
    *,
    pdf_keyword_stats: PdfKeywordStats,
    trusted_hint: bool = False,
    trusted_allowed_negative_terms: Iterable[str] = ("שכר",),
) -> Tuple[bool, Dict]:
    stats = pdf_keyword_stats(path)
    pos_hits = int(stats.get("pos_hits", 0) or 0)
    neg_terms = list(stats.get("neg_terms", []))
    if trusted_hint:
        allowed = set(trusted_allowed_negative_terms)
        filtered_neg = [term for term in neg_terms if term not in allowed]
    else:
        filtered_neg = neg_terms
    neg_hits_effective = len(filtered_neg)

    ok = pos_hits >= 1 and neg_hits_effective == 0
    if trusted_hint and neg_hits_effective == 0 and pos_hits == 0:
        ok = True
    return ok, stats


def decide_pdf_relevance_gmail(
    path: str,
    *,
    pdf_keyword_stats: PdfKeywordStats,
    have_pymupdf: bool,
    trusted_hint: bool = False,
) -> Tuple[bool, Dict]:
    stats = pdf_keyword_stats(path)
    pos_hits = int(stats.get("pos_hits", 0) or 0)
    neg_hits = int(stats.get("neg_hits", 0) or 0)
    strong_hits = int(stats.get("strong_hits", pos_hits) or 0)
    amount_hint = stats.get("amount_hint")
    invoice_id_hint = stats.get("invoice_id_hint")
    weak_only = pos_hits > 0 and strong_hits == 0

    ok = pos_hits >= 1 and neg_hits == 0
    if ok and weak_only:
        ok = True if not have_pymupdf else bool(amount_hint or invoice_id_hint)
    if trusted_hint and pos_hits == 0 and neg_hits == 0:
        ok = True
    return ok, stats
