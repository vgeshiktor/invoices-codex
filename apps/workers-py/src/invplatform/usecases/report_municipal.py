from __future__ import annotations

import re
from typing import Any, List, Optional, Sequence, Tuple

from invplatform.usecases import report_totals


DIRECT_DEBIT_LABELS: tuple[str, ...] = (
    'סה"כ יגבה מהחשבון',
    'סה"כ יגבה',
)

MUNICIPAL_BREAKDOWN_MARKERS: tuple[str, ...] = (
    "חיוב תקופתי",
    "חיוב שנתי",
    "הנחת גביה",
    "הנחת תשלום",
)


def find_municipal_invoice_id(lines: List[str]) -> Tuple[Optional[str], Optional[str]]:
    def prev_text(idx: int) -> Optional[str]:
        for pos in range(idx - 1, -1, -1):
            candidate = lines[pos].strip()
            if candidate:
                return candidate
        return None

    for idx, line in enumerate(lines):
        token = re.sub(r"\s+", "", line)
        if not token.isdigit() or not (8 <= len(token) <= 12):
            continue
        prev = prev_text(idx)
        if prev and re.search(r"[א-תA-Za-z]", prev):
            return token, prev
    return None, None


def extract_amount_from_label(page: Any, label_tokens: Sequence[str]) -> Optional[float]:
    words = page.get_text("words")
    target = None
    for word in words:
        if any(token in word[4] for token in label_tokens):
            target = (word[5], word[6])
            break
    if not target:
        return None
    line_words = [word for word in words if word[5] == target[0] and word[6] == target[1]]
    if not line_words:
        return None
    y_coord = sum(word[1] for word in line_words) / len(line_words)
    digits = [
        word
        for word in words
        if abs(word[1] - y_coord) < 0.6 and re.fullmatch(r"[0-9.,]+", word[4])
    ]
    if not digits:
        return None
    digits = sorted(digits, key=lambda word: word[0])
    raw = "".join(word[4] for word in digits)
    return report_totals.parse_number(raw)


def extract_municipal_breakdown(lines: List[str]) -> Optional[List[float]]:
    values: List[float] = []
    for line in lines:
        if not any(marker in line for marker in MUNICIPAL_BREAKDOWN_MARKERS):
            continue
        amount = report_totals.select_amount(re.findall(r"[\d.,]+", line))
        if amount is None:
            continue
        is_discount = "הנחת" in line or "זיכוי" in line or line.lstrip().startswith("-")
        if is_discount:
            amount = -abs(amount)
        values.append(amount)
    return values or None
