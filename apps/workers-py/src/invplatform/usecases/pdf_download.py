from __future__ import annotations

import re
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import urlparse


DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)
YES_DOMAINS = {"yes.co.il", "www.yes.co.il", "svc.yes.co.il"}

RequestGet = Callable[..., object]


def _extract_filename(content_disposition: str) -> Optional[str]:
    if not content_disposition:
        return None
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disposition, flags=re.I)
    if not match:
        return None
    return match.group(1)


def _default_sanitize_filename(name: str) -> str:
    sanitized = re.sub(r'[\\/:*?"<>|]+', "_", (name or "").strip())
    return sanitized or "link_invoice.pdf"


def _headers_for_attempt(
    url: str,
    *,
    user_agent: str,
    referer: Optional[str],
    include_referer: bool,
    include_yes_headers: bool,
) -> Dict[str, str]:
    headers: Dict[str, str] = {
        "User-Agent": user_agent,
        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1",
    }
    if include_referer and referer:
        headers["Referer"] = referer

    host = (urlparse(url).hostname or "").lower()
    if include_yes_headers and host in YES_DOMAINS:
        headers.setdefault("Origin", "https://www.yes.co.il")
        headers.setdefault("Sec-Fetch-Site", "cross-site")
        headers.setdefault("Sec-Fetch-Mode", "navigate")
        headers.setdefault("Sec-Fetch-Dest", "document")
        headers.setdefault("Sec-Fetch-User", "?1")
        headers.setdefault(
            "sec-ch-ua", '"Not/A)Brand";v="8", "Chromium";v="127", "Google Chrome";v="127"'
        )
        headers.setdefault("sec-ch-ua-platform", '"macOS"')
        headers.setdefault("sec-ch-ua-mobile", "?0")
    return headers


def download_direct_pdf(
    url: str,
    *,
    request_get: RequestGet,
    sanitize_filename: Callable[[str], str] = _default_sanitize_filename,
    referer: Optional[str] = None,
    user_agent: Optional[str] = None,
    timeout_seconds: int = 30,
    include_yes_headers: bool = False,
    fallback_without_referer_on_403: bool = False,
    verbose: bool = False,
) -> Optional[Tuple[str, bytes]]:
    ua = user_agent or DEFAULT_BROWSER_UA
    attempts = [True] if referer else [False]
    if referer and fallback_without_referer_on_403:
        attempts.append(False)

    for include_referer in attempts:
        headers = _headers_for_attempt(
            url,
            user_agent=ua,
            referer=referer,
            include_referer=include_referer,
            include_yes_headers=include_yes_headers,
        )
        try:
            response = request_get(url, headers=headers, timeout=timeout_seconds)
            status_code = int(getattr(response, "status_code", 0))
            response_headers = getattr(response, "headers", {}) or {}
            content = getattr(response, "content", b"") or b""
            content_type = str(response_headers.get("Content-Type") or "").lower()
            if verbose:
                print(
                    f"[direct_pdf] {url} ref={'yes' if include_referer and referer else 'no'} "
                    f"-> status={status_code} ct={response_headers.get('Content-Type')} size={len(content)}"
                )
            if status_code == 403 and include_referer and fallback_without_referer_on_403:
                continue
            is_pdf = "pdf" in content_type or url.lower().endswith(".pdf") or content[:4] == b"%PDF"
            if status_code != 200 or not is_pdf:
                continue
            filename = "link_invoice.pdf"
            extracted = _extract_filename(str(response_headers.get("Content-Disposition") or ""))
            if extracted:
                filename = sanitize_filename(extracted)
                if not filename.lower().endswith(".pdf"):
                    filename += ".pdf"
            return filename, content
        except Exception as exc:  # pragma: no cover - network/remote behavior
            if verbose:
                print(f"[direct_pdf] {url} error: {exc}")
            continue
    return None
