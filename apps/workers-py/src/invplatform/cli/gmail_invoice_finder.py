#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gmail_invoice_finder.v1.0.py
============================

סקריפט להורדת חשבוניות/קבלות מחשבון Gmail, בהשראת הזרימה של graph_invoice_finder:
- חיפוש הודעות עם צרופות/לינקים רלוונטיים בין תאריכים
- הורדת PDF מצורף
- לינקים: הורדה ישירה של PDF, ובזק (myinvoice.bezeq.co.il) דרך Playwright ע"י ניתוח בקשת API (GetAttachedInvoiceById)
- אימות רלוונטיות PDF עם PyMuPDF (מילות מפתח חיוביות/שליליות)
- מניעת דריסה ו־hash de-dup
- דוחות JSON/CSV + Download report
- אפשרות להחריג תיקיית Sent
- דגלי ניטור (--save-candidates/--save-nonmatches/--explain) כמו ב-graph_invoice_finder

תלויות:
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
    pip install requests beautifulsoup4 lxml pymupdf playwright
    playwright install chromium

הכנת OAuth ל-Gmail:
1) צור פרויקט ב-Google Cloud → הפעל Gmail API → צור OAuth Client ID (Desktop App)
2) הורד את credentials.json ושמור לצד הסקריפט
3) בהרצה הראשונה יווצר token.json לאחר אישור בדפדפן

דוגמאות הרצה:
--------------
# בסיסי: טווח תאריכים, שמירה לתיקיית invoices_out
python -m invplatform.cli.gmail_invoice_finder \
  --start-date 2025-09-01 --end-date 2025-10-01 \
  --invoices-dir invoices_out \
  --verify \
  --save-json invoices_gmail.json \
  --save-csv  invoices_gmail.csv \
  --download-report download_report_gmail.json

# החרגת 'נשלח', הרצה ו־trace עבור בזק:
python -m invplatform.cli.gmail_invoice_finder \
  --start-date 2025-09-01 --end-date 2025-10-01 \
  --invoices-dir invoices_out \
  --exclude-sent \
  --verify --debug \
  --bezeq-headful --bezeq-trace --bezeq-screenshots

# חיפוש מותאם ידנית (יגבר על בניית השאילתה האוטומטית):
python -m invplatform.cli.gmail_invoice_finder \
  --gmail-query 'in:anywhere -in:sent -from:me after:2025/09/01 before:2025/10/01 (filename:pdf OR "חשבונית" OR invoice)' \
  --invoices-dir invoices_out --verify

הערות:
- תאריך Gmail בשאילתא בפורמט YYYY/MM/DD (עם /), לא מקפים.
- ברירת מחדל הסקריפט בונה שאילתה טובה לרוב, כולל החרגת 'נשלח' אם ביקשת.
- הסקריפט מייצר quarantine/ לפריטים לא וודאיים אם ביקשת --verify ו/או לא עמדו בסף.
"""

import argparse
import base64
import datetime as dt
import hashlib
import logging
import os
import re
import time
import webbrowser
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, unquote, urlparse

# ==== Google / Gmail API ====
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GReq
from googleapiclient.discovery import build

import requests
from google.auth.exceptions import RefreshError
from bs4 import BeautifulSoup

# Playwright (לבזק)
from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

from ..domain import constants as domain_constants
from ..domain import files as domain_files
from ..domain import pdf as domain_pdf
from ..domain import relevance as domain_relevance
from ..usecases import duplicate_policy, provider_browser, report_io
from ..usecases import pdf_download, pdf_verification
from ..usecases import provider_shared

DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


# --------------------------- Utilities ---------------------------
ensure_dir = domain_files.ensure_dir
sanitize_filename = domain_files.sanitize_filename
short_id_tag = domain_files.short_msg_tag
ensure_unique_path = domain_files.ensure_unique_path
sha256_bytes = domain_files.sha256_bytes
within_domain = domain_relevance.within_domain


def now_utc_iso() -> str:
    return provider_shared.now_utc_iso()


def now_stamp() -> str:
    return provider_shared.now_stamp()


# --------------------------- Keywords & heuristics ---------------------------
EN_POS = domain_constants.EN_POS
HEB_POS = domain_constants.HEB_POS
EN_NEG = domain_constants.EN_NEG
HEB_NEG = domain_constants.HEB_NEG
TRUSTED_PROVIDERS = domain_constants.TRUSTED_PROVIDERS
TRUSTED_SENDER_DOMAINS = domain_constants.TRUSTED_SENDER_DOMAINS
is_municipal_text = domain_relevance.is_municipal_text
body_has_negative = domain_relevance.body_has_negative
body_has_positive = domain_relevance.body_has_positive

YES_DOMAINS = ["yes.co.il", "www.yes.co.il", "svc.yes.co.il"]


# --------------------------- PDF verification ---------------------------
pdf_keyword_stats = domain_pdf.pdf_keyword_stats
pdf_confidence = domain_pdf.pdf_confidence
pdf_text_fingerprint = domain_pdf.text_fingerprint
HAVE_PYMUPDF = getattr(domain_pdf, "HAVE_PYMUPDF", False)


def decide_pdf_relevance(path: str, trusted_hint: bool = False) -> Tuple[bool, Dict]:
    return pdf_verification.decide_pdf_relevance_gmail(
        path,
        pdf_keyword_stats=pdf_keyword_stats,
        have_pymupdf=HAVE_PYMUPDF,
        trusted_hint=trusted_hint,
    )


# --------------------------- Gmail client ---------------------------
class GmailClient:  # pragma: no cover - requires live Google OAuth
    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        self.creds = None
        if os.path.exists(token_path):
            self.creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(GReq())
                except RefreshError:
                    self.creds = None
                except Exception:
                    self.creds = None
            if not self.creds or not self.creds.valid:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                try:
                    self.creds = flow.run_local_server(
                        host="localhost",
                        port=8080,
                        access_type="offline",
                        prompt="consent",
                        include_granted_scopes="true",
                    )
                except webbrowser.Error as e:
                    raise SystemExit(
                        "Gmail OAuth bootstrap failed: no runnable browser in this environment.\n"
                        "Generate/refresh token.json once on a machine with a browser, then rerun.\n"
                        "Example:\n"
                        "  PYTHONPATH=apps/workers-py/src python -m invplatform.cli.gmail_invoice_finder \\\n"
                        "    --start-date 2026-01-01 --end-date 2026-02-01 \\\n"
                        "    --invoices-dir invoices/invoices_gmail_01_2026 --exclude-sent --verify\n"
                        f"Original error: {e}"
                    ) from e

            with open(token_path, "w") as token:
                token.write(self.creds.to_json())
        self.svc = build("gmail", "v1", credentials=self.creds, cache_discovery=False)

    def list_messages(self, q: str, max_results: int = 500, include_spam_trash: bool = False):
        user = "me"
        page_token = None
        fetched = 0
        while True:
            res = (
                self.svc.users()
                .messages()
                .list(
                    userId=user,
                    q=q,
                    maxResults=min(500, max(1, max_results - fetched)),
                    includeSpamTrash=include_spam_trash,
                    pageToken=page_token,
                )
                .execute()
            )
            for m in res.get("messages", []):
                yield m["id"]
                fetched += 1
                if fetched >= max_results:
                    return
            page_token = res.get("nextPageToken")
            if not page_token:
                break

    def get_message(self, msg_id: str) -> Dict:
        return self.svc.users().messages().get(userId="me", id=msg_id, format="full").execute()

    def get_message_metadata(self, msg_id: str) -> Dict:
        return (
            self.svc.users()
            .messages()
            .get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=["Subject", "From"],
            )
            .execute()
        )

    def get_attachment(self, msg_id: str, att_id: str) -> bytes:
        res = (
            self.svc.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=msg_id, id=att_id)
            .execute()
        )
        data = res.get("data", "")
        return base64.urlsafe_b64decode(data.encode("utf-8")) if data else b""


# --------------------------- Gmail helpers ---------------------------
def gmail_date(d: str) -> str:
    # Gmail search uses YYYY/MM/DD
    return d.replace("-", "/")


def build_gmail_query(start_date: str, end_date: str, exclude_sent: bool = True) -> str:
    # בסיס: טווח תאריכים
    parts = [f"after:{gmail_date(start_date)}", f"before:{gmail_date(end_date)}"]
    # לא לכלול נשלח / ממני
    if exclude_sent:
        parts += ["-in:sent", "-from:me"]

    # נרצה רק הודעות עם פוטנציאל חשבוניות: צרופות PDF או מילות מפתח (כולל הטיות עם ה' הידיעה)
    def quote_term(term: str) -> str:
        return f'"{term}"' if any(ch.isspace() for ch in term) else term

    def subject_term(term: str) -> str:
        inner = quote_term(term)
        return f"subject:{inner}"

    heb_terms: List[str] = []
    for term in HEB_POS:
        heb_terms.append(term)
        if term and not term.startswith("ה"):
            heb_terms.append(f"ה{term}")

    keyword_terms: List[str] = ["filename:pdf"]
    for term in heb_terms + EN_POS:
        keyword_terms.append(subject_term(term))
        keyword_terms.append(quote_term(term))

    # הסר כפילויות ושמור על סדר
    keyword_terms = list(dict.fromkeys(keyword_terms))
    keyword_expr = "(" + " OR ".join(keyword_terms) + ")"
    parts.append(keyword_expr)
    # אפשר לא להגביל ל-in:inbox כדי לתפוס ארכיון וכו’:
    parts.append("in:anywhere")
    return " ".join(parts)


def parse_headers(payload: dict) -> Dict[str, str]:
    h = {}
    for it in payload.get("headers") or []:
        name = it.get("name") or ""
        val = it.get("value") or ""
        h[name.lower()] = val
    return h


def extract_parts(payload: dict) -> List[dict]:
    # שטוח כל ה-MIME parts
    res = []

    def walk(p):
        if not p:
            return
        res.append(p)
        for c in p.get("parts") or []:
            walk(c)

    walk(payload)
    return res


def get_body_text(payload: dict) -> Tuple[str, str]:
    # מחזיר (html, plain)
    html, plain = "", ""
    for p in extract_parts(payload):
        mime = (p.get("mimeType") or "").lower()
        body = p.get("body") or {}
        data = body.get("data")
        if not data:
            continue
        try:
            raw = base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")
        except Exception:
            continue
        if mime == "text/html":
            html += raw + "\n"
        elif mime == "text/plain":
            plain += raw + "\n"
    return html, plain


def extract_links_from_html(html: str) -> List[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    links = [a["href"] for a in soup.find_all("a", href=True)]
    # גם מ-img map וכד’
    for tag in soup.find_all(["area"]):
        href = tag.get("href")
        if href:
            links.append(href)
    # ייחודיות
    return list(dict.fromkeys(links))


def extract_links_from_text(text: str) -> List[str]:
    urls = re.findall(r'https?://[^\s<>"\)\]]+', text or "", flags=re.I)
    return list(dict.fromkeys(urls))


def normalize_link(u: str) -> str:
    if not u:
        return u
    try:
        parsed = urlparse(u)
    except Exception:
        return u
    host = (parsed.hostname or "").lower()
    if host in {"www.google.com", "google.com"} and parsed.path.startswith("/url"):
        qs = parse_qs(parsed.query)
        for key in ("url", "q"):
            target = qs.get(key)
            if target:
                return unquote(target[0])
    return u


def sender_domain(address: str) -> str:
    if not address:
        return ""
    m = re.search(r"<([^>]+)>", address)
    email = (m.group(1) if m else address).strip().lower()
    if "@" not in email:
        return ""
    return email.split("@")[-1]


def is_trusted_sender(address: str) -> bool:
    domain = sender_domain(address)
    return bool(domain and any(domain.endswith(d) for d in TRUSTED_SENDER_DOMAINS))


def _decode_data_url(data_url: str) -> Optional[bytes]:
    m = re.match(r"data:([^;]+);base64,(.+)", data_url, flags=re.I)
    if not m:
        return None
    try:
        blob = base64.b64decode(m.group(2))
    except Exception:
        return None
    return blob or None


def sha256_file(path: str) -> Optional[str]:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def load_existing_hash_index(inv_dir: str) -> Dict[str, str]:
    index: Dict[str, str] = {}
    if not os.path.isdir(inv_dir):
        return index
    for root, dirs, files in os.walk(inv_dir):
        dirs[:] = [d for d in dirs if d not in {"_tmp", "quarantine"}]
        for name in files:
            if not name.lower().endswith(".pdf"):
                continue
            path = os.path.join(root, name)
            digest = sha256_file(path)
            if digest and digest not in index:
                index[digest] = path
    return index


def normalized_stem(name: str) -> str:
    stem = os.path.splitext(os.path.basename(name))[0]
    m = re.match(r"^(.*)__\d+$", stem)
    return m.group(1) if m else stem


def load_existing_stems(inv_dir: str) -> Set[str]:
    stems: Set[str] = set()
    if not os.path.isdir(inv_dir):
        return stems
    for root, dirs, files in os.walk(inv_dir):
        dirs[:] = [d for d in dirs if d not in {"_tmp", "quarantine", "duplicates"}]
        for name in files:
            if not name.lower().endswith(".pdf"):
                continue
            stems.add(normalized_stem(name))
    return stems


def load_existing_text_fps(inv_dir: str) -> Dict[str, str]:
    fps: Dict[str, str] = {}
    if not HAVE_PYMUPDF or not os.path.isdir(inv_dir):
        return fps
    for root, dirs, files in os.walk(inv_dir):
        dirs[:] = [d for d in dirs if d not in {"_tmp", "quarantine", "duplicates"}]
        for name in files:
            if not name.lower().endswith(".pdf"):
                continue
            path = os.path.join(root, name)
            fp = pdf_text_fingerprint(path)
            if fp and fp not in fps:
                fps[fp] = path
    return fps


def build_tagged_name(name: str, msg_tag: str) -> Tuple[str, str]:
    safe = sanitize_filename(name)
    stem, ext = os.path.splitext(safe)
    if not ext:
        ext = ".pdf"
    tagged = f"{stem}__{msg_tag}{ext}"
    return tagged, normalized_stem(tagged)


# --------------------------- Direct PDF via requests ---------------------------
def download_direct_pdf(
    url: str, referer: Optional[str] = None, ua: Optional[str] = None, verbose: bool = False
) -> Optional[Tuple[str, bytes]]:
    return pdf_download.download_direct_pdf(
        url,
        request_get=requests.get,
        sanitize_filename=sanitize_filename,
        referer=referer,
        user_agent=ua or DEFAULT_BROWSER_UA,
        include_yes_headers=True,
        fallback_without_referer_on_403=True,
        verbose=verbose,
    )


def yes_fetch_with_browser(  # pragma: no cover - requires real Playwright/browser
    url: str, headless: bool, verbose: bool = False
) -> Dict[str, object]:
    return provider_browser.yes_fetch_with_browser(
        url=url,
        headless=headless,
        verbose=verbose,
        sync_playwright=sync_playwright,
        playwright_timeout_error=PWTimeout,
        user_agent=DEFAULT_BROWSER_UA,
        sanitize_filename=sanitize_filename,
        decode_data_url=_decode_data_url,
    )


# --------------------------- Bezeq (Playwright) ---------------------------
def normalize_myinvoice_url(u: str) -> str:
    return provider_shared.normalize_myinvoice_url(u)


def bezeq_fetch_with_api_sniff(  # pragma: no cover - Playwright/network heavy
    url: str,
    out_dir: str,
    headless: bool,
    keep_trace: bool,
    take_screens: bool,
    verbose: bool,
) -> Dict:
    return provider_browser.bezeq_fetch_with_api_sniff(
        url=url,
        out_dir=out_dir,
        headless=headless,
        keep_trace=keep_trace,
        take_screens=take_screens,
        verbose=verbose,
        sync_playwright=sync_playwright,
        playwright_timeout_error=PWTimeout,
        normalize_url=normalize_myinvoice_url,
        now_stamp=now_stamp,
        sanitize_filename=sanitize_filename,
    )


# --------------------------- Flow helpers ---------------------------
def links_from_message(html: str, plain: str) -> List[str]:
    links = extract_links_from_html(html) + extract_links_from_text(plain)
    normalized: List[str] = []
    for u in links:
        if not u.startswith("http"):
            continue
        nu = normalize_link(u)
        if nu and nu.startswith("http"):
            normalized.append(nu)
    # ייחודיות
    return list(dict.fromkeys(normalized))


def should_consider_message(subject: str, preview: str) -> bool:
    t = f"{subject or ''} {preview or ''}"
    if body_has_negative(t):
        return False
    return body_has_positive(t) or is_municipal_text(t)


def payload_has_pdf_attachment(payload: dict) -> bool:
    for p in extract_parts(payload):
        body = p.get("body") or {}
        att_id = body.get("attachmentId")
        if not att_id:
            continue
        mime = (p.get("mimeType") or "").lower()
        filename = (p.get("filename") or "").lower()
        if "pdf" in mime or filename.endswith(".pdf"):
            return True
    return False


def should_fetch_full_message(
    subject: str,
    preview: str,
    sender_trusted: bool,
    metadata_payload: dict,
    disable_prefilter: bool = False,
) -> bool:
    if disable_prefilter:
        return True
    if sender_trusted or should_consider_message(subject, preview):
        return True
    return payload_has_pdf_attachment(metadata_payload)


# --------------------------- Main ---------------------------
def main(argv: Optional[List[str]] = None) -> int:  # pragma: no cover - CLI orchestration
    ap = argparse.ArgumentParser(description="Gmail Invoice Finder v1.0")
    ap.add_argument("--credentials", default="credentials.json")
    ap.add_argument("--token", default="token.json")

    ap.add_argument("--gmail-query", default=None, help="שאילתת Gmail מותאמת (עוקף בנייה אוטומטית)")
    ap.add_argument("--start-date", required=False, help="YYYY-MM-DD (לשילוב בשאילתא הנבנית)")
    ap.add_argument("--end-date", required=False, help="YYYY-MM-DD (לשילוב בשאילתא הנבנית)")
    ap.add_argument("--exclude-sent", action="store_true", help="החרגת נשלח/ממני בשאילתת Gmail")

    ap.add_argument("--invoices-dir", default="./invoices_out")
    ap.add_argument("--keep-quarantine", action="store_true")
    ap.add_argument("--download-report", default="download_report_gmail.json")
    ap.add_argument("--save-json", default=None)
    ap.add_argument("--save-csv", default=None)
    ap.add_argument("--save-candidates", default=None, help="Dump all raw PDF candidates to JSON")
    ap.add_argument(
        "--save-nonmatches", default=None, help="Dump rejected message metadata to JSON"
    )
    ap.add_argument("--max-messages", type=int, default=1000)
    ap.add_argument(
        "--disable-metadata-prefilter",
        action="store_true",
        help="Fetch full Gmail message bodies for all hits (slower, legacy behavior).",
    )

    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--explain", action="store_true")

    # Playwright / Bezeq
    ap.add_argument(
        "--bezeq-headful",
        action="store_true",
        help="פתח חלון Playwright (בזק/YES) במקום ריצה headless",
    )
    ap.add_argument("--bezeq-trace", action="store_true")
    ap.add_argument("--bezeq-screenshots", action="store_true")  # לא בשימוש ישיר כאן, דגל עתידי
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format="%(message)s")

    inv_dir = ensure_dir(args.invoices_dir)
    quarant_dir = ensure_dir(os.path.join(inv_dir, "quarantine")) if args.keep_quarantine else None
    tmp_dir = ensure_dir(os.path.join(inv_dir, "_tmp"))

    # בניית שאילתא
    if args.gmail_query:
        query = args.gmail_query
    else:
        if not (args.start_date and args.end_date):
            print("כשלא מספקים --gmail-query חובה לתת --start-date ו--end-date לבניית השאילתא.")
            return 2
        query = build_gmail_query(args.start_date, args.end_date, exclude_sent=args.exclude_sent)

    logging.info(f"Gmail query: {query}")

    gc = GmailClient(credentials_path=args.credentials, token_path=args.token)

    saved_rows: List[Dict] = []
    rejected_rows: List[Dict] = []
    download_report: List[Dict] = []
    candidate_entries: List[Dict] = []
    seen_hashes: Set[str] = set()
    hash_to_saved_path: Dict[str, str] = {}

    existing_index = load_existing_hash_index(inv_dir)
    if existing_index:
        seen_hashes.update(existing_index.keys())
        hash_to_saved_path.update(existing_index)
    existing_stems = load_existing_stems(inv_dir)
    existing_fps = load_existing_text_fps(inv_dir)
    if existing_fps:
        seen_text_fps: Set[str] = set(existing_fps.keys())
        text_fp_to_path: Dict[str, str] = dict(existing_fps)
    else:
        seen_text_fps = set()
        text_fp_to_path = {}

    def record_candidate(entry: Dict) -> None:
        if args.save_candidates:
            candidate_entries.append(entry)
        if args.explain:
            label = entry.get("name") or entry.get("url") or entry.get("type")
            decision = entry.get("decision") or ""
            reason = entry.get("reason") or ""
            confidence = entry.get("confidence")
            parts = [decision]
            if reason:
                parts.append(reason)
            if confidence is not None:
                parts.append(f"conf={confidence:.2f}")
            summary = ", ".join(p for p in parts if p)
            logging.info(
                "    candidate[%s] %s => %s", entry.get("type"), label, summary or "recorded"
            )

    def record_nonmatch(entry: Dict) -> None:
        rejected_rows.append(entry)
        if args.explain:
            subj = entry.get("subject") or entry.get("id")
            logging.info("    nonmatch[%s]: %s", subj, entry.get("reason"))

    idx = 0
    full_fetch_count = 0
    prefilter_skipped = 0
    scan_start = time.monotonic()
    for msg_id in gc.list_messages(query, max_results=args.max_messages):
        idx += 1
        try:
            msg_meta = gc.get_message_metadata(msg_id)
        except Exception as e:
            record_nonmatch({"id": msg_id, "reason": f"get_message_metadata_fail:{e}"})
            continue

        meta_payload = msg_meta.get("payload") or {}
        meta_headers = parse_headers(meta_payload)
        subject = meta_headers.get("subject", "")
        from_addr = meta_headers.get("from", "")
        internal_ts = int(msg_meta.get("internalDate", "0")) // 1000
        received = dt.datetime.utcfromtimestamp(internal_ts).isoformat() if internal_ts else ""
        snippet = msg_meta.get("snippet") or ""
        sender_trusted = is_trusted_sender(from_addr)

        if not should_fetch_full_message(
            subject=subject,
            preview=snippet,
            sender_trusted=sender_trusted,
            metadata_payload=meta_payload,
            disable_prefilter=args.disable_metadata_prefilter,
        ):
            prefilter_skipped += 1
            record_nonmatch(
                {
                    "id": msg_id,
                    "subject": subject,
                    "from": from_addr,
                    "receivedDateTime": received,
                    "reason": "prefilter_non_invoice",
                }
            )
            continue

        try:
            msg = gc.get_message(msg_id)
            full_fetch_count += 1
        except Exception as e:
            record_nonmatch(
                {
                    "id": msg_id,
                    "subject": subject,
                    "from": from_addr,
                    "receivedDateTime": received,
                    "reason": f"get_message_full_fail:{e}",
                }
            )
            continue

        payload = msg.get("payload") or {}
        headers = parse_headers(payload)
        subject = headers.get("subject", subject)
        from_addr = headers.get("from", from_addr)
        internal_ts = int(msg.get("internalDate", "0")) // 1000
        received = dt.datetime.utcfromtimestamp(internal_ts).isoformat() if internal_ts else ""
        snippet = msg.get("snippet") or ""
        sender_trusted = is_trusted_sender(from_addr)

        logging.info(f"[{idx}] {subject} | {from_addr} | {received}")

        # מסנן גבוה: תעדף רק הודעות עם ערך פוטנציאלי
        if not should_consider_message(subject, snippet):
            # אם יש PDF מצורף, עדיין נשקול – נמשיך לבדוק attach
            pass

        msg_tag = short_id_tag(msg_id)
        any_saved = False
        message_rejected = False

        # ---- Attachments ----
        parts = extract_parts(payload)
        for p in parts:
            mime = (p.get("mimeType") or "").lower()
            body = p.get("body") or {}
            filename = p.get("filename") or ""
            att_id = body.get("attachmentId")
            if not att_id:
                continue
            if "pdf" not in mime and not filename.lower().endswith(".pdf"):
                continue
            candidate = {
                "msg_id": msg_id,
                "type": "attachment",
                "name": filename,
                "mimeType": mime,
                "subject": subject,
                "from": from_addr,
                "receivedDateTime": received,
            }
            try:
                blob = gc.get_attachment(msg_id, att_id)
                if not blob:
                    continue
                h = sha256_bytes(blob)
                candidate["sha256"] = h
                if duplicate_policy.duplicate_by_hash(h, seen_hashes):
                    dup_path = duplicate_policy.duplicate_of_hash(h, hash_to_saved_path)
                    download_report.append(
                        {
                            "msg_id": msg_id,
                            "type": "attachment",
                            "name": filename,
                            "skip": "duplicate_hash",
                            **({"duplicate_of": dup_path} if dup_path else {}),
                        }
                    )
                    candidate.update(
                        {
                            "decision": "skip",
                            "reason": "duplicate_hash",
                            **({"duplicate_of": dup_path} if dup_path else {}),
                        }
                    )
                    record_candidate(candidate)
                    continue

                tmp_path = os.path.join(tmp_dir, f"tmp__{msg_tag}.pdf")
                with open(tmp_path, "wb") as f:
                    f.write(blob)

                trusted_hint = sender_trusted
                if args.verify:
                    ok, stats = decide_pdf_relevance(tmp_path, trusted_hint=trusted_hint)
                else:
                    ok, stats = True, {"pos_hits": 1, "neg_hits": 0}
                confidence = pdf_confidence(stats)

                text_fp = pdf_text_fingerprint(tmp_path) if HAVE_PYMUPDF else None
                candidate["text_fingerprint"] = text_fp

                if text_fp:
                    if duplicate_policy.duplicate_by_text_fingerprint(text_fp, seen_text_fps):
                        dup_path = duplicate_policy.duplicate_of_text(text_fp, text_fp_to_path)
                        download_report.append(
                            {
                                "msg_id": msg_id,
                                "type": "attachment",
                                "name": filename,
                                "skip": "duplicate_text",
                                **({"duplicate_of": dup_path} if dup_path else {}),
                            }
                        )
                        candidate.update(
                            {
                                "decision": "skip",
                                "reason": "duplicate_text",
                                **({"duplicate_of": dup_path} if dup_path else {}),
                            }
                        )
                        record_candidate(candidate)
                        os.remove(tmp_path)
                        continue
                candidate.update(
                    {"stats": stats, "confidence": confidence, "trusted_hint": trusted_hint}
                )

                if not ok:
                    if quarant_dir:
                        out_q = ensure_unique_path(quarant_dir, filename or "file.pdf", tag=msg_tag)
                        os.replace(tmp_path, out_q)
                        download_report.append(
                            {
                                "msg_id": msg_id,
                                "type": "attachment",
                                "name": filename,
                                "path": out_q,
                                "ok": False,
                                "stats": stats,
                                "confidence": confidence,
                            }
                        )
                        candidate.update(
                            {"decision": "quarantine", "reason": "verify_failed", "path": out_q}
                        )
                    else:
                        os.remove(tmp_path)
                        download_report.append(
                            {
                                "msg_id": msg_id,
                                "type": "attachment",
                                "name": filename,
                                "reject": "verify_failed",
                                "stats": stats,
                                "confidence": confidence,
                            }
                        )
                        candidate.update({"decision": "reject", "reason": "verify_failed"})
                    record_candidate(candidate)
                    continue

                out_path = ensure_unique_path(inv_dir, filename or "invoice.pdf", tag=msg_tag)
                os.replace(tmp_path, out_path)
                duplicate_policy.remember_hash(h, out_path, seen_hashes, hash_to_saved_path)
                duplicate_policy.remember_text_fingerprint(
                    text_fp, out_path, seen_text_fps, text_fp_to_path
                )
                download_report.append(
                    {
                        "msg_id": msg_id,
                        "type": "attachment",
                        "name": filename,
                        "path": out_path,
                        "ok": True,
                        "stats": stats,
                        "confidence": confidence,
                    }
                )
                candidate.update({"decision": "saved", "path": out_path})
                record_candidate(candidate)
                saved_rows.append(
                    {
                        "id": msg_id,
                        "subject": subject,
                        "from": from_addr,
                        "receivedDateTime": received,
                        "source": "attachment",
                        "path": out_path,
                    }
                )
                any_saved = True
            except Exception as e:
                download_report.append(
                    {
                        "msg_id": msg_id,
                        "type": "attachment",
                        "name": filename,
                        "reject": f"attach_download_fail:{e}",
                    }
                )
                candidate.update({"decision": "error", "reason": f"attach_download_fail:{e}"})
                record_candidate(candidate)

        # ---- Links (אם לא ניצלנו מצורף) ----
        if not any_saved:
            html, plain = get_body_text(payload)
            links = links_from_message(html, plain)
            for u in links:
                candidate = {
                    "msg_id": msg_id,
                    "type": "link_direct_pdf",
                    "url": u,
                    "subject": subject,
                    "from": from_addr,
                    "receivedDateTime": received,
                }
                is_bezeq = within_domain(
                    u, ["myinvoice.bezeq.co.il", "my.bezeq.co.il", "bmy.bezeq.co.il"]
                )
                is_yes = within_domain(u, YES_DOMAINS)
                # הורדה ישירה אם PDF
                r = download_direct_pdf(
                    u,
                    referer="https://mail.google.com/",
                    ua=DEFAULT_BROWSER_UA,
                    verbose=args.debug,
                )
                if not r and is_yes:
                    browser_out = yes_fetch_with_browser(
                        u, headless=not args.bezeq_headful, verbose=args.debug
                    )
                    if browser_out.get("notes"):
                        candidate["notes"] = browser_out.get("notes")
                    if browser_out.get("ok"):
                        candidate["type"] = "link_browser_pdf"
                        r = (browser_out["name"], browser_out["blob"])
                if r:
                    name, blob = r
                    h = sha256_bytes(blob)
                    candidate.update({"name": name, "sha256": h})
                    if duplicate_policy.duplicate_by_hash(h, seen_hashes):
                        dup_path = duplicate_policy.duplicate_of_hash(h, hash_to_saved_path)
                        download_report.append(
                            {
                                "msg_id": msg_id,
                                "type": "link",
                                "url": u,
                                "skip": "duplicate_hash",
                                **({"duplicate_of": dup_path} if dup_path else {}),
                            }
                        )
                        candidate.update(
                            {
                                "decision": "skip",
                                "reason": "duplicate_hash",
                                **({"duplicate_of": dup_path} if dup_path else {}),
                            }
                        )
                        record_candidate(candidate)
                        continue
                    tmp_path = os.path.join(tmp_dir, f"tmp__{msg_tag}.pdf")
                    with open(tmp_path, "wb") as f:
                        f.write(blob)

                    trusted_hint = (
                        sender_trusted
                        or within_domain(u, TRUSTED_PROVIDERS)
                        or is_municipal_text(subject + " " + snippet)
                    )
                    ok, stats = (True, {"pos_hits": 1, "neg_hits": 0})
                    if args.verify:
                        ok, stats = decide_pdf_relevance(tmp_path, trusted_hint=trusted_hint)
                    confidence = pdf_confidence(stats)
                    text_fp = pdf_text_fingerprint(tmp_path) if HAVE_PYMUPDF else None
                    candidate["text_fingerprint"] = text_fp
                    if duplicate_policy.duplicate_by_text_fingerprint(text_fp, seen_text_fps):
                        dup_path = duplicate_policy.duplicate_of_text(text_fp, text_fp_to_path)
                        download_report.append(
                            {
                                "msg_id": msg_id,
                                "type": "link",
                                "url": u,
                                "skip": "duplicate_text",
                                **({"duplicate_of": dup_path} if dup_path else {}),
                            }
                        )
                        candidate.update(
                            {
                                "decision": "skip",
                                "reason": "duplicate_text",
                                **({"duplicate_of": dup_path} if dup_path else {}),
                            }
                        )
                        record_candidate(candidate)
                        os.remove(tmp_path)
                        continue
                    candidate.update(
                        {"stats": stats, "confidence": confidence, "trusted_hint": trusted_hint}
                    )

                    if not ok:
                        if quarant_dir:
                            out_q = ensure_unique_path(quarant_dir, name, tag=msg_tag)
                            os.replace(tmp_path, out_q)
                            download_report.append(
                                {
                                    "msg_id": msg_id,
                                    "type": "link",
                                    "url": u,
                                    "path": out_q,
                                    "ok": False,
                                    "stats": stats,
                                    "confidence": confidence,
                                }
                            )
                            candidate.update(
                                {"decision": "quarantine", "reason": "verify_failed", "path": out_q}
                            )
                        else:
                            os.remove(tmp_path)
                            download_report.append(
                                {
                                    "msg_id": msg_id,
                                    "type": "link",
                                    "url": u,
                                    "reject": "verify_failed",
                                    "stats": stats,
                                    "confidence": confidence,
                                }
                            )
                            candidate.update({"decision": "reject", "reason": "verify_failed"})
                        record_candidate(candidate)
                        continue

                    tagged_name, stem_key = build_tagged_name(name, msg_tag)
                    if duplicate_policy.duplicate_by_stem(stem_key, existing_stems):
                        os.remove(tmp_path)
                        download_report.append(
                            {
                                "msg_id": msg_id,
                                "type": "link",
                                "url": u,
                                "skip": "duplicate_stem",
                                "stem": stem_key,
                            }
                        )
                        candidate.update({"decision": "skip", "reason": "duplicate_stem"})
                        record_candidate(candidate)
                        continue

                    out_path = ensure_unique_path(inv_dir, tagged_name)
                    os.replace(tmp_path, out_path)
                    duplicate_policy.remember_hash(h, out_path, seen_hashes, hash_to_saved_path)
                    duplicate_policy.remember_stem(stem_key, existing_stems)
                    duplicate_policy.remember_text_fingerprint(
                        text_fp, out_path, seen_text_fps, text_fp_to_path
                    )
                    download_report.append(
                        {
                            "msg_id": msg_id,
                            "type": "link",
                            "url": u,
                            "path": out_path,
                            "ok": True,
                            "stats": stats,
                            "confidence": confidence,
                        }
                    )
                    candidate.update({"decision": "saved", "path": out_path})
                    record_candidate(candidate)
                    saved_rows.append(
                        {
                            "id": msg_id,
                            "subject": subject,
                            "from": from_addr,
                            "receivedDateTime": received,
                            "source": candidate.get("type", "link_direct_pdf"),
                            "path": out_path,
                        }
                    )
                    any_saved = True
                    break

                # בזק – Flutter
                if is_bezeq:
                    candidate = {
                        "msg_id": msg_id,
                        "type": "bezeq_api",
                        "url": u,
                        "subject": subject,
                        "from": from_addr,
                        "receivedDateTime": received,
                    }
                    out = bezeq_fetch_with_api_sniff(
                        url=u,
                        out_dir=inv_dir,
                        headless=not args.bezeq_headful,
                        keep_trace=args.bezeq_trace,
                        take_screens=args.bezeq_screenshots,
                        verbose=args.debug,
                    )
                    candidate["notes"] = out.get("notes", [])
                    if out.get("ok") and out.get("path"):
                        name, blob = out["path"]
                        h = sha256_bytes(blob)
                        candidate["sha256"] = h
                        if duplicate_policy.duplicate_by_hash(h, seen_hashes):
                            dup_path = duplicate_policy.duplicate_of_hash(h, hash_to_saved_path)
                            download_report.append(
                                {
                                    "msg_id": msg_id,
                                    "type": "link",
                                    "url": u,
                                    "skip": "duplicate_hash",
                                    **({"duplicate_of": dup_path} if dup_path else {}),
                                }
                            )
                            candidate.update(
                                {
                                    "decision": "skip",
                                    "reason": "duplicate_hash",
                                    **({"duplicate_of": dup_path} if dup_path else {}),
                                }
                            )
                            record_candidate(candidate)
                            continue

                        tmp_path = os.path.join(tmp_dir, f"tmp__{msg_tag}.pdf")
                        with open(tmp_path, "wb") as f:
                            f.write(blob)

                        trusted_hint = True
                        if args.verify:
                            ok, stats = decide_pdf_relevance(tmp_path, trusted_hint=trusted_hint)
                        else:
                            ok, stats = True, {"pos_hits": 1, "neg_hits": 0}
                        confidence = pdf_confidence(stats)
                        text_fp = pdf_text_fingerprint(tmp_path) if HAVE_PYMUPDF else None
                        candidate["text_fingerprint"] = text_fp
                        if duplicate_policy.duplicate_by_text_fingerprint(text_fp, seen_text_fps):
                            dup_path = duplicate_policy.duplicate_of_text(text_fp, text_fp_to_path)
                            download_report.append(
                                {
                                    "msg_id": msg_id,
                                    "type": "link",
                                    "url": u,
                                    "skip": "duplicate_text",
                                    **({"duplicate_of": dup_path} if dup_path else {}),
                                }
                            )
                            candidate.update(
                                {
                                    "decision": "skip",
                                    "reason": "duplicate_text",
                                    **({"duplicate_of": dup_path} if dup_path else {}),
                                }
                            )
                            record_candidate(candidate)
                            os.remove(tmp_path)
                            continue
                        candidate.update(
                            {
                                "stats": stats,
                                "confidence": confidence,
                                "trusted_hint": trusted_hint,
                            }
                        )

                        if not ok:
                            if quarant_dir:
                                out_q = ensure_unique_path(quarant_dir, name, tag=msg_tag)
                                os.replace(tmp_path, out_q)
                                download_report.append(
                                    {
                                        "msg_id": msg_id,
                                        "type": "link",
                                        "url": u,
                                        "path": out_q,
                                        "ok": False,
                                        "stats": stats,
                                        "notes": out.get("notes", []),
                                        "confidence": confidence,
                                    }
                                )
                                candidate.update(
                                    {
                                        "decision": "quarantine",
                                        "reason": "verify_failed",
                                        "path": out_q,
                                    }
                                )
                            else:
                                os.remove(tmp_path)
                                download_report.append(
                                    {
                                        "msg_id": msg_id,
                                        "type": "link",
                                        "url": u,
                                        "reject": "verify_failed",
                                        "stats": stats,
                                        "notes": out.get("notes", []),
                                        "confidence": confidence,
                                    }
                                )
                            candidate.update({"decision": "reject", "reason": "verify_failed"})
                            record_candidate(candidate)
                            continue

                        tagged_name, stem_key = build_tagged_name(name, msg_tag)
                        if duplicate_policy.duplicate_by_stem(stem_key, existing_stems):
                            os.remove(tmp_path)
                            download_report.append(
                                {
                                    "msg_id": msg_id,
                                    "type": "link",
                                    "url": u,
                                    "skip": "duplicate_stem",
                                    "stem": stem_key,
                                }
                            )
                            candidate.update({"decision": "skip", "reason": "duplicate_stem"})
                            record_candidate(candidate)
                            continue

                        out_path = ensure_unique_path(inv_dir, tagged_name)
                        os.replace(tmp_path, out_path)
                        duplicate_policy.remember_hash(h, out_path, seen_hashes, hash_to_saved_path)
                        duplicate_policy.remember_stem(stem_key, existing_stems)
                        duplicate_policy.remember_text_fingerprint(
                            text_fp, out_path, seen_text_fps, text_fp_to_path
                        )
                        download_report.append(
                            {
                                "msg_id": msg_id,
                                "type": "link",
                                "url": u,
                                "path": out_path,
                                "ok": True,
                                "stats": stats,
                                "notes": out.get("notes", []),
                                "confidence": confidence,
                            }
                        )
                        candidate.update({"decision": "saved", "path": out_path})
                        record_candidate(candidate)
                        saved_rows.append(
                            {
                                "id": msg_id,
                                "subject": subject,
                                "from": from_addr,
                                "receivedDateTime": received,
                                "source": "bezeq_api",
                                "path": out_path,
                            }
                        )
                        any_saved = True
                        break
                    else:
                        if out.get("notes"):
                            download_report.append(
                                {
                                    "msg_id": msg_id,
                                    "type": "link",
                                    "url": u,
                                    "notes": out.get("notes", []),
                                    "ok": False,
                                    "reject": "bezeq_no_pdf",
                                }
                            )
                        candidate.update({"decision": "no_pdf", "reason": "bezeq_no_pdf"})
                        record_candidate(candidate)
                    continue

                candidate.update({"decision": "download_failed"})
                record_candidate(candidate)
                continue

            if not any_saved and links:
                record_nonmatch(
                    {
                        "id": msg_id,
                        "subject": subject,
                        "from": from_addr,
                        "receivedDateTime": received,
                        "reason": "links_no_pdf",
                    }
                )
                message_rejected = True

        if not any_saved and not message_rejected:
            record_nonmatch(
                {
                    "id": msg_id,
                    "subject": subject,
                    "from": from_addr,
                    "receivedDateTime": received,
                    "reason": "no_attach_no_pdf_links",
                }
            )

    scan_seconds = time.monotonic() - scan_start
    logging.info(
        "[GMAIL_STAGE] scanned=%d full_fetch=%d prefilter_skipped=%d duration=%ss",
        idx,
        full_fetch_count,
        prefilter_skipped,
        f"{scan_seconds:.1f}",
    )

    # ----- Reports -----
    if args.download_report:
        report_io.write_json(
            args.download_report,
            {"saved": saved_rows, "rejected": rejected_rows, "ts": now_utc_iso()},
        )
        print(f"Download report → {args.download_report}")

    if args.save_json:
        report_io.write_json(args.save_json, saved_rows)
        print(f"Saved messages JSON → {args.save_json}")

    if args.save_csv:
        fields = ["id", "subject", "from", "receivedDateTime", "source", "path"]
        report_io.write_dict_rows_csv(args.save_csv, saved_rows, fields)
        print(f"Saved messages CSV → {args.save_csv}")

    if args.save_candidates:
        report_io.write_json(args.save_candidates, candidate_entries)
        print(f"Saved candidates → {args.save_candidates}")

    if args.save_nonmatches:
        report_io.write_json(args.save_nonmatches, rejected_rows)
        print(f"Saved nonmatches → {args.save_nonmatches}")

    print(f"Done. Saved {len(saved_rows)} invoices; Rejected {len(rejected_rows)}.")
    return 0


def run(argv: Optional[List[str]] = None) -> int:
    """Programmatic entry point for callers that need an exit code."""
    try:
        return int(main(argv))
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 1


if __name__ == "__main__":
    raise SystemExit(main())
