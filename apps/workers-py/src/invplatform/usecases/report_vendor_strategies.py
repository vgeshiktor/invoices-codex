from __future__ import annotations

import re
from typing import List, Optional, Tuple


Amount = Optional[float]


KNOWN_VENDOR_MARKERS: Tuple[Tuple[str, str], ...] = (
    ("יול ימר", "רמי לוי תקשורת"),
    ("פרטנר", 'חברת פרטנר תקשורת בע"מ'),
    ("רנטרפ", 'חברת פרטנר תקשורת בע"מ'),
    ("partner communications", 'חברת פרטנר תקשורת בע"מ'),
    ("בזק-ג'ן בע\"מ", "בזק-ג'ן בע\"מ"),
    ('בזק-ג׳ן בע"מ', 'בזק-ג׳ן בע"מ'),
    ("מ\"עב ן'ג-קזב", 'בזק-ג׳ן בע"מ'),
    ('דן חברה לתחבורה ציבורית בע"מ', 'דן חברה לתחבורה ציבורית בע"מ'),
    ('מ"עב תירוביצ הרובחתל הרבח ןד', 'דן חברה לתחבורה ציבורית בע"מ'),
    ("משרד התחבורה והבטיחות בדרכים", "משרד התחבורה והבטיחות בדרכים"),
    ("םיכרדב תוחיטבהו הרובחתה דרשמ", "משרד התחבורה והבטיחות בדרכים"),
    ("אופק הפקות", "אופק הפקות"),
    ("הפקות אופק", "אופק הפקות"),
    ("אופק", "אופק הפקות"),
    ("ofek productions", "אופק הפקות"),
    ("סטינג", "STINGTV"),
    ("stingtv", "STINGTV"),
    ("סי יתורש", "STINGTV"),
    ("יתורש סי", "STINGTV"),
    ("just simple ltd", "JUST SIMPLE LTD"),
)

PETAH_TIKVA_KEYWORDS: Tuple[str, ...] = ("פתח תק", "הווקת חתפ")
PETAH_TIKVA_MUNICIPAL_MARKERS: Tuple[str, ...] = (
    "עיריית",
    "עריית",
    "עירייה",
    "עיריה",
    "ערייה",
    "עריה",
    "עירית",
    "ערית",
    "העירייה",
    "העיריה",
    "תיעיר",
    "תיעירת",
    "רשות מקומית",
)
PUBLIC_TRANSPORT_HEBREW_MARKERS: Tuple[str, ...] = (
    "תירוביצ הרובחת",
    "תירוביצה הרובחת",
    "תירוביצה הרובחתה",
    "התחבורה הציבורית",
    "וק-בר",
    "רב-קו",
)
PUBLIC_TRANSPORT_LATIN_MARKERS: Tuple[str, ...] = (
    "ravpass",
    "rav-kav",
    "ravkav",
    "rav kav",
)
PUBLIC_TRANSPORT_INVOICE_FOR = "רב-קו - טעינה"


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


def normalize_invoice_for_value(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    cleaned = raw.strip().strip(":\"'").strip()
    cleaned = re.sub(r"^[\d\s'\"`.,-]+", "", cleaned)
    cleaned = cleaned.strip()
    if not cleaned or not re.search(r"[A-Za-zא-ת]", cleaned):
        return None
    match = re.search(r"מס-?\s*(\d{4})\s+([א-תA-Za-z\s\"']{2,})", cleaned)
    if match:
        desc = match.group(2).strip()
        year = match.group(1)
        if desc:
            cleaned = f"{desc} {year}"
    if "ארנונה לעסקים" in cleaned:
        return "ארנונה לעסקים"
    if "ארנונה" in cleaned:
        return "ארנונה"
    cleaned = re.sub(r"\s*-\s*", " - ", cleaned)
    cleaned = re.sub(r'מ["״]\s*בע', 'בע"מ', cleaned)
    cleaned = re.sub(r'בע["״]\s*מ', 'בע"מ', cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned or None


def detect_known_vendor(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    normalized_text = text.casefold()
    for marker, label in KNOWN_VENDOR_MARKERS:
        if marker.casefold() in normalized_text:
            return label
    return None


def has_public_transport_marker(text: Optional[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if any(marker in text for marker in PUBLIC_TRANSPORT_HEBREW_MARKERS):
        return True
    return any(marker in lowered for marker in PUBLIC_TRANSPORT_LATIN_MARKERS)


def looks_like_petah_tikva_municipality(text: Optional[str]) -> bool:
    if not text:
        return False
    if not any(marker in text for marker in PETAH_TIKVA_KEYWORDS):
        return False
    return any(marker in text for marker in PETAH_TIKVA_MUNICIPAL_MARKERS)


def infer_invoice_from(lines: List[str], text: Optional[str] = None) -> Optional[str]:
    candidate: Optional[str] = None
    for line in lines:
        if 'מ"עב' in line or 'בע"מ' in line or "Ltd" in line or "חברה" in line:
            candidate = line
            break
    if candidate is None:
        for line in lines[:15]:
            if "www" in line or "@" in line or "cid:" in line:
                continue
            if line.isdigit():
                continue
            if re.search(r"[א-תA-Za-z]", line):
                candidate = line
                break
    vendor = detect_known_vendor(text)
    if vendor:
        return vendor
    if text:
        normalized_text = re.sub(r"\s+", " ", text)
        if all(term in normalized_text for term in ("קרן", "מדריכת", "הורים", "ותינוקות")):
            return "קרן-מדריכת הורים ותינוקות"
        match = re.search(r"מאת\s+([^\n]+)", text)
        if match:
            candidate = match.group(1).strip()
            for stop in (":", "לכבוד", "שם"):
                if stop in candidate:
                    candidate = candidate.split(stop, 1)[0].strip()
            if candidate:
                return candidate
        match = re.search(r"ע[יר]יית\s+[^\n]{2,40}", text)
        if match:
            result = match.group(0).strip().replace("עריית", "עיריית")
            return result
        if looks_like_petah_tikva_municipality(text):
            return "עיריית פתח תקווה"
    return candidate


def extract_keren_invoice_for(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    normalized = " ".join(text.split())
    match = re.search(r"פירוט\s+(20\d{2})\s+([א-ת]+)\s+תנועה\s+חוג", normalized)
    if match:
        year, month = match.groups()
        return f"חוג תנועה {month} {year}"
    return None


def extract_partner_invoice_for(lines: List[str], raw_text: Optional[str] = None) -> Optional[str]:
    stop_markers = ['סה"כ', "סהכ", 'כ"הס']
    for idx, line in enumerate(lines):
        if "פירוט" in line and "חיובים" in line and "זיכויים" in line and "החשבון" in line:
            details: List[str] = []
            for lookahead in range(1, 8):
                pos = idx + lookahead
                if pos >= len(lines):
                    break
                candidate = lines[pos].strip()
                if not candidate:
                    continue
                if any(marker in candidate for marker in stop_markers):
                    break
                if re.search(r"[א-תA-Za-z]", candidate):
                    details.append(candidate)
                if len(details) >= 4:
                    break
            if details:
                return " | ".join(details)
            return "פירוט חיובים וזיכויים לתקופת החשבון"

    if raw_text:
        segment_match = re.search(
            r"פירוט\s+חיובים\s+וזיכויים\s+לתקופת\s+החשבון\s+(.*?)\s+סה\"?כ\s+חיובי\s+החשבון",
            raw_text,
            flags=re.DOTALL,
        )
        if segment_match:
            segment = segment_match.group(1)
            entries: List[str] = []
            match_mobile = re.search(r"(\d+)מנויי\s*סלולר", segment)
            if match_mobile:
                entries.append(f"{match_mobile.group(1)} מנויי סלולר")
            match_transport = re.search(r"(\d+)מנוי\s*תמסורת\s*([\d-]+)", segment)
            if match_transport:
                count, ident = match_transport.groups()
                entries.append(f"{count} מנוי תמסורת {ident}")
            if re.search(r"תנועות\s+כלליות\s+בחשבון\s+הלקוח", segment):
                entries.append("תנועות כלליות בחשבון הלקוח")
            if entries:
                return " | ".join(entries)
            return "פירוט חיובים וזיכויים לתקופת החשבון"
    return None


def extract_ofek_invoice_for(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    normalized = " ".join(text.split())
    month_pattern = r"(אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר|ינואר|פברואר|מרץ|אפריל|מאי|יוני|יולי)"
    variants = (
        (r"חוג\s+תיאטרון\s+חודש\s+" + month_pattern, "חוג תיאטרון חודש {}"),
        (month_pattern + r"\s+חודש\s+תיאטרון\s+חוג", "חוג תיאטרון חודש {}"),
        (r"חוג\s+חודש\s+" + month_pattern, "חוג חודש {}"),
        (month_pattern + r"\s+חודש\s+חוג", "חוג חודש {}"),
    )
    summaries: List[str] = []
    for pattern, template in variants:
        for month in re.findall(pattern, normalized):
            value = template.format(month)
            if value not in summaries:
                summaries.append(value)
    if summaries:
        return " | ".join(summaries)
    return None


def extract_stingtv_invoice_for(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    normalized = " ".join(text.split())
    phrase_variants = {
        "שירותי תוכן בינלאומיים": [
            "שירותי תוכן בינלאומיים",
            "םיימואלניב ןכות יתוריש",
        ],
        "ספריות וערוצי פרימיום": [
            "ספריות וערוצי פרימיום",
            "םוימירפ יצורעו תוירפס",
        ],
    }
    found: List[str] = []
    for canonical, variants in phrase_variants.items():
        if any(variant in normalized for variant in variants):
            found.append(canonical)
    if found:
        return " | ".join(found)
    return None


def extract_stingtv_breakdown(text: Optional[str]) -> List[float]:
    if not text:
        return []
    normalized = " ".join(text.split())
    start = normalized.find("ןובשחה טוריפ")
    if start == -1:
        return []
    end_markers = ["עצבמב לולכ", "תמלשומה", "Sample"]
    end = len(normalized)
    for marker in end_markers:
        idx = normalized.find(marker, start)
        if idx != -1:
            end = min(end, idx)
    section = normalized[start:end]
    values: List[float] = []
    for token in re.findall(r"-?\d[\d.,]*", section):
        amount = parse_number(token)
        if amount is not None:
            values.append(amount)
    return values


def extract_just_simple_invoice_for(
    lines: List[str], raw_text: Optional[str] = None
) -> Optional[str]:
    source = raw_text or " ".join(lines)
    if not source:
        return None
    normalized = " ".join(source.split())
    if "just simple ltd" not in normalized.casefold():
        return None

    period_match = re.search(r"\b(?:0?[1-9]|1[0-2])/\d{2}\b", normalized)
    period = period_match.group(0) if period_match else None
    has_core_terms = all(term in normalized for term in ("תפעול", "פנסיוני", "שוטף"))
    if has_core_terms and period:
        return f"תפעול פנסיוני- שוטף {period}"

    for idx, line in enumerate(lines):
        if "תאור" not in line and "תיאור" not in line:
            continue
        collected: List[str] = []
        for lookahead in range(1, 8):
            pos = idx + lookahead
            if pos >= len(lines):
                break
            candidate = lines[pos].strip()
            if not candidate:
                continue
            if any(marker in candidate for marker in ("כמות", 'סה"כ', "סכום", "פירוט", "אופן")):
                break
            collected.append(candidate)
        segment = " ".join(collected)
        if all(term in segment for term in ("תפעול", "פנסיוני", "שוטף")):
            if period is None:
                segment_period = re.search(r"\b(?:0?[1-9]|1[0-2])/\d{2}\b", segment)
                period = segment_period.group(0) if segment_period else None
            if period:
                return f"תפעול פנסיוני- שוטף {period}"
    return None


def infer_invoice_for(lines: List[str], text: Optional[str] = None) -> Optional[str]:
    if has_public_transport_marker(text):
        return PUBLIC_TRANSPORT_INVOICE_FOR
    keren_summary = extract_keren_invoice_for(text)
    if keren_summary:
        return keren_summary
    ofek_summary = extract_ofek_invoice_for(text)
    if ofek_summary:
        return ofek_summary
    stingtv_summary = extract_stingtv_invoice_for(text)
    if stingtv_summary:
        return stingtv_summary
    just_simple_summary = extract_just_simple_invoice_for(lines, text)
    if just_simple_summary:
        return just_simple_summary
    partner_summary = extract_partner_invoice_for(lines, text)
    if partner_summary:
        return partner_summary
    if ":םיטרפ" in " ".join(lines):
        try:
            start = lines.index(":םיטרפ")
        except ValueError:
            start = -1
        if start >= 0:
            collected: List[str] = []
            for ln in lines[start + 1 :]:
                if any(marker in ln for marker in ("טקמ", 'כ"הס', 'סה"כ', "כסה")):
                    break
                if len(ln) > 2:
                    collected.append(ln)
            if collected:
                return " | ".join(collected[:5])
    for idx, line in enumerate(lines):
        if "פירוט החיוב" in line or "פירוט החיובים" in line:
            tail = normalize_invoice_for_value(
                line.split("פירוט החיוב", 1)[-1]
                if "פירוט החיוב" in line
                else line.split("פירוט החיובים", 1)[-1]
            )
            if tail and "נכס" not in tail:
                return tail
            for lookahead in range(1, 8):
                if idx + lookahead < len(lines):
                    raw_line = lines[idx + lookahead].strip()
                    skip_markers = [
                        'סה"כ',
                        "סהכ",
                        "תיאור",
                        "כתובת",
                        "מס' זיהוי",
                        "מספר זיהוי",
                        "מס'",
                    ]
                    if any(marker in raw_line for marker in skip_markers):
                        continue
                    candidate = normalize_invoice_for_value(raw_line)
                    if candidate:
                        return candidate
    for line in lines:
        if " עבור " in line or " - " in line:
            if len(line) < 200:
                if re.search(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", line):
                    continue
                normalized = normalize_invoice_for_value(line)
                return normalized or line
    if text:
        if "ארנונה לעסקים" in text:
            return "ארנונה לעסקים"
        if "ארנונה" in text:
            return "ארנונה"
    return None
