from __future__ import annotations

from collections import Counter
import re
from typing import Iterable, List, Optional, Tuple, TypedDict

from invplatform.usecases import report_vendor_strategies


Amount = Optional[float]


class TotalsResult(TypedDict):
    invoice_total: Optional[float]
    invoice_vat: Optional[float]
    vat_rate: Optional[float]
    municipal: bool
    breakdown_sum: Optional[float]
    breakdown_values: Optional[List[float]]
    base_before_vat: Optional[float]


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


def amount_near_markers(
    text: str, patterns: Iterable[str], window: int = 120, prefer: str = "max"
) -> Amount:
    def extract_values(tokens: List[str]) -> List[Tuple[float, str]]:
        values: List[Tuple[float, str]] = []
        for tok in tokens:
            amount = parse_number(tok)
            if amount is not None and amount > 0:
                values.append((amount, tok))
        return values

    def choose(values: List[Tuple[float, str]]) -> Amount:
        if not values:
            return None
        decimals = [val for val in values if "." in val[1] or "," in val[1]]
        pool = decimals if decimals else values
        amounts = [val for val, _ in pool]
        if prefer == "min":
            return min(amounts)
        return max(amounts)

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.MULTILINE):
            tail = text[match.end() : match.end() + window]
            head = text[max(0, match.start() - window) : match.start()]
            values = extract_values(re.findall(r"[\d.,]+", tail))
            values += extract_values(re.findall(r"[\d.,]+", head))
            amount = choose(values)
            if amount is not None:
                return amount
    return None


def numeric_candidates(line: str) -> List[tuple[str, bool]]:
    candidates: List[tuple[str, bool]] = []
    for match in re.finditer(r"[\d.,]+", line):
        token = match.group(0)
        start, end = match.start(), match.end()
        before = line[max(0, start - 2) : start]
        after = line[end : end + 2]
        is_percent = "%" in before or "%" in after
        candidates.append((token, is_percent))
    return candidates


def numeric_values_near_marker(lines: List[str], marker: str, window: int = 4) -> List[float]:
    values: List[float] = []
    for idx, line in enumerate(lines):
        if marker in line:
            for token, is_percent in numeric_candidates(line):
                if is_percent:
                    continue
                amount = parse_number(token)
                if amount is not None:
                    values.append(amount)
            for offset in range(1, window + 1):
                for pos in (idx - offset, idx + offset):
                    if 0 <= pos < len(lines):
                        for token, is_percent in numeric_candidates(lines[pos]):
                            if is_percent:
                                continue
                            amount = parse_number(token)
                            if amount is not None:
                                values.append(amount)
            break
    return values


def normalize_marker_text(line: str) -> str:
    return line.replace("״", '"').replace("׳", "'").replace(" ", "")


def is_total_with_vat_line(line: str) -> bool:
    compact = normalize_marker_text(line)
    has_total = 'כ"סה' in compact or 'סה"כ' in compact
    has_vat = 'מ"מע' in compact or 'מע"מ' in compact
    return has_total and has_vat and "כולל" in compact


def is_vat_percent_line(line: str) -> bool:
    compact = normalize_marker_text(line)
    has_vat = 'מ"מע' in compact or 'מע"מ' in compact
    return has_vat and "%" in compact


def amount_from_line_end(line: str) -> Amount:
    tokens = [tok for tok, is_percent in numeric_candidates(line) if not is_percent]
    if not tokens:
        return None
    for token in reversed(tokens):
        if "." in token or "," in token:
            amount = parse_number(token)
            if amount is not None:
                return amount
    return parse_number(tokens[-1])


def repeated_currency_total(currency_tokens: List[str]) -> Amount:
    amounts = []
    for token in currency_tokens:
        amount = parse_number(token)
        if amount is None or amount <= 0:
            continue
        amounts.append(round(amount, 2))
    if not amounts:
        return None
    counts = Counter(amounts)
    repeated = [(count, value) for value, count in counts.items() if count >= 2 and value >= 50]
    if repeated:
        repeated.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return repeated[0][1]
    large = [value for value in amounts if value >= 50]
    if large:
        return max(large)
    return max(amounts)


def extract_total_from_total_with_vat_lines(lines: List[str], currency_tokens: List[str]) -> Amount:
    for line in lines:
        if is_total_with_vat_line(line):
            amount = amount_from_line_end(line)
            if amount is not None:
                return amount
    for idx in range(len(lines)):
        window = lines[idx : idx + 4]
        if not window:
            continue
        has_total = any(
            'כ"סה' in normalize_marker_text(line) or 'סה"כ' in normalize_marker_text(line)
            for line in window
        )
        has_vat = any(
            'מ"מע' in normalize_marker_text(line) or 'מע"מ' in normalize_marker_text(line)
            for line in window
        )
        has_including = any("כולל" in line for line in window)
        if has_total and has_vat and has_including:
            window_amounts = [amount_from_line_end(line) for line in window]
            numeric_amounts = [
                value for value in window_amounts if value is not None and value >= 20
            ]
            if numeric_amounts:
                return max(numeric_amounts)
            return repeated_currency_total(currency_tokens)
    return None


def extract_vat_from_percent_lines(
    lines: List[str],
    currency_tokens: List[str],
    *,
    total: Amount,
    explicit_vat_rate: Optional[float],
) -> Amount:
    target_rate = explicit_vat_rate
    for idx, line in enumerate(lines):
        if not is_vat_percent_line(line):
            continue
        amount = amount_from_line_end(line)
        if amount is not None:
            return amount
        if idx + 1 < len(lines):
            next_amount = amount_from_line_end(lines[idx + 1])
            if next_amount is not None:
                return next_amount
        if target_rate is None:
            for token, is_percent in numeric_candidates(line):
                if not is_percent:
                    continue
                parsed_rate = parse_number(token)
                if parsed_rate is not None and 0 < parsed_rate <= 100:
                    target_rate = parsed_rate
                    break
    if total is None or target_rate is None:
        return None
    candidates: List[Tuple[float, float]] = []
    for token in currency_tokens:
        amount = parse_number(token)
        if amount is None or amount <= 0 or amount >= total:
            continue
        rate = vat_rate_estimate(total, amount)
        if rate is None:
            continue
        candidates.append((abs(rate - target_rate), amount))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    if candidates[0][0] > 1.0:
        return None
    return candidates[0][1]


def sum_numeric_block(
    lines: List[str],
    start_markers: Iterable[str],
    end_markers: Iterable[str],
) -> Tuple[Optional[float], List[float]]:
    collecting = False
    total = 0.0
    found = False
    values: List[float] = []
    for line in lines:
        if not collecting and any(marker in line for marker in start_markers):
            collecting = True
            continue
        if collecting:
            stripped = line.strip()
            if any(end in line for end in end_markers):
                break
            token = stripped
            if re.match(r"^-?\d[\d,]*(?:\.\d+)?$", token):
                val = parse_number(token)
                if val is not None:
                    total += val
                    values.append(val)
                    found = True
    return (total if found else None, values)


def find_amount_before_marker(
    lines: List[str], marker: str, *, prefer_inline: bool = False
) -> Amount:
    for idx, line in enumerate(lines):
        if marker in line:
            inline_candidates = numeric_candidates(line)
            line_has_percent = "%" in line
            preferred = [tok for tok, is_percent in inline_candidates if not is_percent]
            tokens = preferred if preferred else [tok for tok, _ in inline_candidates]
            if line_has_percent:
                tokens = []
            amount = select_amount(tokens[::-1]) if tokens else None
            if amount is not None:
                return amount
            if prefer_inline:
                continue
            for lookback in range(1, 4):
                if idx - lookback >= 0:
                    candidate = lines[idx - lookback]
                    if not prefer_inline and "/" in candidate and "₪" not in candidate:
                        continue
                    candidate_tokens = numeric_candidates(candidate)
                    preferred_tokens = [
                        tok for tok, is_percent in candidate_tokens if not is_percent
                    ]
                    tokens = (
                        preferred_tokens
                        if preferred_tokens
                        else [tok for tok, _ in candidate_tokens]
                    )
                    amount = select_amount(tokens[::-1]) if tokens else None
                    if amount is not None:
                        return amount
            for lookahead in range(1, 4):
                if idx + lookahead < len(lines):
                    candidate = lines[idx + lookahead]
                    candidate_tokens = numeric_candidates(candidate)
                    preferred_tokens = [
                        tok for tok, is_percent in candidate_tokens if not is_percent
                    ]
                    tokens = (
                        preferred_tokens
                        if preferred_tokens
                        else [tok for tok, _ in candidate_tokens]
                    )
                    amount = select_amount(tokens[::-1]) if tokens else None
                    if amount is not None:
                        return amount
            break
    return None


def vat_rate_estimate(total: Optional[float], vat: Optional[float]) -> Optional[float]:
    if total is None or vat is None or total == 0:
        return None
    base = total - vat
    if base <= 0:
        return None
    return round((vat / base) * 100, 2)


def extract_vat_rate_from_text(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    vat_marker = r"מ\s*[\"״']?\s*ע\s*[\"״']?\s*מ"
    patterns = [
        rf"([\d.,]+)\s*%[^\n]{{0,15}}?{vat_marker}",
        rf"{vat_marker}[^%\d]{{0,15}}?([\d.,]+)\s*%",
        r"VAT[^%\d]{0,15}?([\d.,]+)\s*%",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = parse_number(match.group(1))
            if value is not None:
                return round(value, 2)
    return None


def infer_totals(
    lines: List[str],
    text: str,
    *,
    debug: bool = False,
    label: str = "",
    pdfminer_lines: Optional[List[str]] = None,
) -> TotalsResult:
    def dbg(msg: str) -> None:
        if debug:
            prefix = f"[debug][{label}] " if label else "[debug] "
            print(prefix + msg)

    def numbers_after_marker(marker: str, limit: int = 10) -> Tuple[List[float], List[float]]:
        best: List[float] = []
        best_len = 0
        best_max: Optional[float] = None
        aggregated: List[float] = []
        for idx, line in enumerate(lines):
            if marker not in line:
                continue
            collected: List[float] = []
            for offset in range(1, limit + 1):
                pos = idx + offset
                if pos >= len(lines):
                    break
                token = lines[pos]
                if "." not in token and "," not in token and "₪" not in token:
                    if collected:
                        break
                    continue
                value = parse_number(token)
                if value is None:
                    if collected:
                        break
                    continue
                collected.append(value)
            if collected:
                aggregated.extend(collected)
                col_max = max(collected)
                size = len(collected)
                if (
                    not best
                    or (size >= 3 > best_len)
                    or (size >= 3 and best_len >= 3 and (best_max is None or col_max > best_max))
                    or (best_len < 3 and size < 3 and (best_max is None or col_max > best_max))
                ):
                    best = collected
                    best_len = size
                    best_max = col_max
        return best, aggregated

    total_block, total_values = numbers_after_marker('כ"הס', limit=16)
    block_alt, values_alt = numbers_after_marker('סה"כ', limit=16)
    if block_alt and (not total_block or max(block_alt) > max(total_block)):
        total_block = block_alt
    total_values.extend(values_alt)
    block_max = max(total_block) if total_block else None

    total = find_amount_before_marker(lines, 'םלוש כ"הס', prefer_inline=True)
    if total is None:
        total = find_amount_before_marker(lines, 'םולשתל כ"הס', prefer_inline=True)
    if total is None:
        total = find_amount_before_marker(lines, "םולשתל", prefer_inline=True)
    base_before_vat = find_amount_before_marker(lines, 'מ"עמ ינפל', prefer_inline=True)
    base_candidates = numeric_values_near_marker(lines, 'מ"עמ ינפל')
    vat = find_amount_before_marker(lines, 'לע מ"עמ')
    if vat is None:
        vat = find_amount_before_marker(lines, 'מ"עמ ')
    vat_candidates = numeric_values_near_marker(lines, 'לע מ"עמ')
    explicit_vat_rate = extract_vat_rate_from_text(text)
    currency_tokens = re.findall(r"₪\s*([\d.,]+)", text)
    dbg(
        f"initial total={total}, base_before_vat={base_before_vat}, "
        f"base_candidates={base_candidates}, vat_initial={vat}, "
        f"vat_candidates={vat_candidates}, explicit_vat_rate={explicit_vat_rate}"
    )

    if total is None:
        for marker in ('סה"כ', "סה״כ", "סהכ", 'סה"כ לתשלום', 'סה"כ לתשלום בש"ח'):
            total = find_amount_before_marker(lines, marker)
            if total is not None:
                break
    if total is None:
        match = re.search(r"סה.?\"?כ.?[:\-]?\s*([\d.,]+)", text)
        if match:
            total = parse_number(match.group(1))
    if total is None:
        patterns = [
            r"סה.?\"?כ.? ?לתשלום[^\d]*([\d.,]+)",
            r"([\d.,]+)\s+סה.?\"?כ.? ?לתשלום",
            r"סה.?\"?כ.? ?לתשלום(?:.|\n){0,40}?([\d.,]+)",
            r"כ.?\"?הס[^\n]{0,40}?םולשתל[^\n]{0,40}?ח.?\"?ש[^\n]{0,40}?מ\"?עמ[^\d]*([\d.,]+)",
            r"([\d.,]+)\s+מ\"?עמ[^\n]{0,40}?ח.?\"?ש[^\n]{0,40}?םולשתל[^\n]{0,40}?כ.?\"?הס",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
            if match:
                total = parse_number(match.group(1))
                if total is not None:
                    break
    if total is None:
        total = amount_near_markers(
            text,
            [
                r"סה.?\"?כ.? ?לתשלום",
                r"כ.?\"?הס[^\n]{0,40}?םולשתל[^\n]{0,40}?מ\"?עמ",
                r"ח.?\"?ש[^\n]{0,20}?םולשתל",
            ],
            prefer="max",
        )
    if total is None:
        match = re.search(
            r"סה.?\"?כ.? ?יגבה[^:]*:\s*([0-9,\.\s]+?)(?:\n|$)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            token = re.sub(r"\s+", "", match.group(1))
            total = parse_number(token)
    if total is None or (total is not None and total <= 5):
        match = re.search(
            r"סה.{0,4}?יגבה[^:]*:\s*((?:.|\n)*?)\n\s*4",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            block = match.group(1)
            token = re.sub(r"[^0-9.,]", "", block)
            total = parse_number(token)
            if (total is None or total < 50 or "\n" in block) and token:
                reversed_token = token[::-1]
                alt = parse_number(reversed_token)
                if alt is not None:
                    total = alt
    if total is None:
        match = re.search(r"סה.?\"?כ.? ?יגבה[^0-9]+([\d.,]+)", text)
        if match:
            total = parse_number(match.group(1))
    if block_max:
        if total is None or (block_max > total and block_max - total > 50):
            total = block_max
    if total is None:
        matches = re.findall(r"₪\s*([\d.,]+)\s*[:\-]?\s*כ[\"״']?הס", text)
        amounts = [parse_number(token) for token in matches]
        numeric = [val for val in amounts if val is not None]
        if numeric:
            total = max(numeric)
    fallback_total = select_amount(currency_tokens[::-1])
    if total is None:
        total = fallback_total
    elif fallback_total and fallback_total < total and (total - fallback_total) > 50:
        total = fallback_total
    elif total is not None and total <= 5 and fallback_total and fallback_total > total:
        total = fallback_total
    marker_total = extract_total_from_total_with_vat_lines(lines, currency_tokens)
    if marker_total is not None and (total is None or abs(marker_total - total) > 1.0):
        total = marker_total
    marker_vat = extract_vat_from_percent_lines(
        lines,
        currency_tokens,
        total=total,
        explicit_vat_rate=explicit_vat_rate,
    )
    if marker_vat is not None and (vat is None or abs(marker_vat - vat) > 1.0):
        vat = marker_vat
    if base_candidates:
        candidates = base_candidates[:]
        if total is not None:
            below_total = [val for val in candidates if val < total]
            if below_total:
                candidates = below_total
        if candidates:
            base_before_vat = max(candidates)
    dbg(f"total after heuristics={total}, base_before_vat={base_before_vat}")

    if base_before_vat is None and total is not None and total_values:
        approx_base = total / 1.18 if total > 0 else None
        if approx_base:
            candidates = [val for val in total_values if 0 < val < total]
            if candidates:
                base_before_vat = min(candidates, key=lambda val: abs(val - approx_base))

    if vat is None:
        vat_patterns = [
            r"סה.?\"?כ.? ?מע\"?מ[^\d]*([\d.,]+)",
            r"([\d.,]+)\s+סה.?\"?כ.? ?מע\"?מ",
            r"מ\"?עמ[^\n]{0,30}?כ.?\"?הס[^\d]*([\d.,]+)",
            r"([\d.,]+)\s+כ.?\"?הס[^\n]{0,30}?מ\"?עמ",
        ]
        for pattern in vat_patterns:
            match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
            if match:
                vat = parse_number(match.group(1))
                if vat is not None:
                    break
    if vat is None:
        vat = amount_near_markers(
            text,
            [
                r"סה.?\"?כ.? ?מע\"?מ",
                r"מ\"?עמ[^\n]{0,30}?כ.?\"?הס",
            ],
            prefer="min",
        )
    if vat is None:
        for line in lines:
            if 'מ"עמ' in line:
                if 'מ"עמל' in line and "₪" not in line and "%" not in line:
                    continue
                tokens = re.findall(r"[\d.,]+", line)
                amount = select_amount(tokens[::-1])
                if amount is not None:
                    vat = amount
                    break
            if vat is not None:
                break

    if total is not None and vat_candidates:
        filtered_vat = sorted(val for val in vat_candidates if 0 < val < total)
        replacement_vat = None
        for candidate in filtered_vat:
            rate_candidate = vat_rate_estimate(total, candidate)
            if rate_candidate is None or abs(rate_candidate - 18.0) < 1.0:
                replacement_vat = candidate
                break
        if replacement_vat is None and filtered_vat:
            replacement_vat = filtered_vat[0]
        if replacement_vat is not None:
            vat = replacement_vat

    if vat is None and total is not None and base_before_vat is not None:
        candidate_vat = round(total - base_before_vat, 2)
        if candidate_vat >= 0:
            vat = candidate_vat

    if vat is not None and total is not None and vat > total:
        vat = None
    if vat is None:
        vat = amount_near_markers(
            text,
            [
                r"סה.?\"?כ.? ?מע\"?מ",
                r"מ\"?עמ[^\n]{0,30}?כ.?\"?הס",
            ],
            prefer="min",
        )

    if (
        vat is None
        and total is not None
        and base_before_vat is not None
        and base_before_vat < total
    ):
        vat_candidate = round(total - base_before_vat, 2)
        if vat_candidate >= 0:
            vat = vat_candidate

    currency_amounts: List[float] = []
    if total is not None or vat is not None:
        for token in currency_tokens:
            amount = parse_number(token)
            if amount is not None:
                currency_amounts.append(amount)
    dbg(f"currency_amounts={currency_amounts}")

    if vat is None and total is not None:
        smaller = [amt for amt in currency_amounts if amt < total]
        if smaller:
            vat_candidate = round(total - max(smaller), 2)
            if vat_candidate >= 0:
                vat = vat_candidate
    elif vat is not None and total is not None:
        smaller = [amt for amt in currency_amounts if amt < total]
        if smaller:
            vat_candidate = round(total - max(smaller), 2)
            if 0 < vat_candidate < vat:
                vat = vat_candidate

    rate = vat_rate_estimate(total, vat)
    dbg(f"vat after heuristics={vat}, vat_rate={rate}")
    if (
        rate is not None
        and total is not None
        and base_before_vat is not None
        and base_before_vat < total
        and abs(rate - 18.0) > 1.0
    ):
        recalculated_vat = round(total - base_before_vat, 2)
        if recalculated_vat >= 0:
            vat = recalculated_vat
            dbg(f"vat replaced via base diff → {vat}")

    if total is not None and vat is not None:
        candidate_base = round(total - vat, 2)
        if candidate_base >= 0:
            if base_before_vat is None or abs(base_before_vat - candidate_base) > 1.0:
                base_before_vat = candidate_base

    municipal_markers = [
        "ארנונה",
        "עיריית",
        "רשות מקומית",
        "תאגיד מים",
        "onecity",
    ]
    is_municipal = any(marker in text for marker in municipal_markers)
    if not is_municipal:
        if (("פתח תק" in text) or ("הווקת חתפ" in text)) and ("חוב" in text):
            is_municipal = True
    block_source = pdfminer_lines or lines
    block_sum, breakdown_values = sum_numeric_block(
        block_source,
        ['ח"שב', "חשב כ"],
        [
            "סכנה",
            "סה",
            'סה"',
            "סה''כ יגבה",
            'סה"כ יגבה',
            'סה"כ יגבה',
            "Sample text",
            "ללוכ בויח",
            "ןובשחה טוריפ",
            "עצבמב לולכ",
        ],
    )
    stingtv_breakdown = report_vendor_strategies.extract_stingtv_breakdown(text)
    if stingtv_breakdown:
        block_sum = sum(stingtv_breakdown) if stingtv_breakdown else None
        breakdown_values = stingtv_breakdown
    if is_municipal:
        if block_sum is not None:
            if total is None or total < 50 or abs(total - block_sum) > 1.0:
                total = block_sum
                dbg(f"municipal total derived from block sum={total}")
        vat = 0.0
        dbg("municipal invoice detected → forcing VAT=0")

    return {
        "invoice_total": total,
        "invoice_vat": vat,
        "vat_rate": explicit_vat_rate
        if explicit_vat_rate is not None
        else vat_rate_estimate(total, vat),
        "municipal": is_municipal,
        "breakdown_sum": block_sum,
        "breakdown_values": breakdown_values,
        "base_before_vat": base_before_vat,
    }
