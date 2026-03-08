from __future__ import annotations

import os
import re
import time
from typing import Any, Callable, ContextManager, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse


PlaywrightFactory = Callable[[], ContextManager[Any]]
NormalizeURL = Callable[[str], str]
NowStamp = Callable[[], str]
SanitizeFilename = Callable[[str], str]
DecodeDataURL = Callable[[str], Optional[bytes]]


def bezeq_fetch_with_api_sniff(
    *,
    url: str,
    out_dir: str,
    headless: bool,
    keep_trace: bool,
    take_screens: bool,
    verbose: bool,
    sync_playwright: PlaywrightFactory,
    playwright_timeout_error: type[Exception],
    normalize_url: NormalizeURL,
    now_stamp: NowStamp,
    sanitize_filename: SanitizeFilename,
) -> Dict:
    _ = take_screens  # retained for API compatibility
    res: Dict[str, Any] = {"ok": False, "path": None, "notes": [], "normalized_url": None}

    def note(message: str) -> None:
        if verbose:
            print(message)
        res["notes"].append(message)

    normalized_url = normalize_url(url)
    res["normalized_url"] = normalized_url

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=headless, args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                accept_downloads=True,
                locale="he-IL",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
                ),
                extra_http_headers={"Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7"},
            )
            if keep_trace:
                context.tracing.start(screenshots=True, snapshots=True, sources=False)

            api_urls: List[str] = []

            def on_console(message):
                try:
                    msg_type = (
                        message.type()
                        if callable(getattr(message, "type", None))
                        else str(getattr(message, "type", ""))
                    )
                    text = (
                        message.text()
                        if callable(getattr(message, "text", None))
                        else str(getattr(message, "text", ""))
                    )
                    note(f"console:{msg_type}:{text}")
                    if "GetAttachedInvoiceById" in text:
                        m = re.search(r"https?://[^\s\"']+GetAttachedInvoiceById[^\s\"']+", text)
                        if m:
                            api_urls.append(m.group(0))
                except Exception:
                    pass

            def on_request(req):
                try:
                    if "GetAttachedInvoiceById" in (req.url or ""):
                        api_urls.append(req.url)
                except Exception:
                    pass

            def on_response(resp):
                try:
                    if "GetAttachedInvoiceById" in (resp.url or ""):
                        api_urls.append(resp.url)
                except Exception:
                    pass

            page = context.new_page()
            page.on("console", on_console)
            context.on("request", on_request)
            context.on("response", on_response)

            try:
                page.goto(normalized_url, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=12000)
            except playwright_timeout_error:
                note("networkidle_timeout")

            def direct_api(candidate_url: str) -> Optional[Tuple[str, bytes]]:
                try:
                    resp = context.request.get(candidate_url, headers={"Referer": normalized_url})
                    body = resp.body()
                    content_type = (resp.headers.get("content-type") or "").lower()
                    if (content_type and "pdf" in content_type) or body[:4] == b"%PDF":
                        name = "bezeq_invoice_api.pdf"
                        query = parse_qs(urlparse(candidate_url).query)
                        invoice_id = (query.get("InvoiceId") or [""])[0]
                        cd = resp.headers.get("content-disposition") or ""
                        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, flags=re.I)
                        if m:
                            name = sanitize_filename(m.group(1))
                            if not name.lower().endswith(".pdf"):
                                name += ".pdf"
                        if invoice_id:
                            stem, ext = os.path.splitext(name)
                            name = f"{stem}__{invoice_id}{ext or '.pdf'}"
                        return name, body
                except Exception as exc:
                    note(f"direct_api_err:{exc}")
                return None

            for candidate_url in list(dict.fromkeys(api_urls)):
                item = direct_api(candidate_url)
                if item:
                    res["ok"] = True
                    res["path"] = item
                    break

            if not res["ok"]:
                try:
                    for selector in [
                        'text="להורדה"',
                        "text=להורדה",
                        'text="לצפייה"',
                        "text=לצפייה",
                        '[aria-label*="הורדה"]',
                        '[title*="הורדה"]',
                    ]:
                        try:
                            page.locator(selector).first.click(timeout=2000)
                            time.sleep(1.0)
                            break
                        except Exception:
                            continue
                except Exception:
                    pass
                for candidate_url in list(dict.fromkeys(api_urls)):
                    item = direct_api(candidate_url)
                    if item:
                        res["ok"] = True
                        res["path"] = item
                        break

            if keep_trace:
                try:
                    context.tracing.stop(
                        path=os.path.join(out_dir, f"bezeq_trace_{now_stamp()}.zip")
                    )
                except Exception:
                    pass
            context.close()
            browser.close()
    except Exception as exc:  # pragma: no cover - Playwright/runtime specific
        msg = str(exc)
        note(f"playwright_error:{msg}")
        if "executable doesn't exist" in msg.lower() or "playwright install" in msg.lower():
            note(
                "playwright chromium browser missing; run `playwright install chromium` and retry."
            )

    return res


def yes_fetch_with_browser(
    *,
    url: str,
    headless: bool,
    verbose: bool,
    sync_playwright: PlaywrightFactory,
    playwright_timeout_error: type[Exception],
    user_agent: str,
    sanitize_filename: SanitizeFilename,
    decode_data_url: DecodeDataURL,
) -> Dict[str, object]:
    res: Dict[str, Any] = {"ok": False, "notes": []}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=headless, args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                locale="he-IL",
                user_agent=user_agent,
                extra_http_headers={"Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7"},
            )

            pdf_blob: Optional[bytes] = None
            pdf_name: Optional[str] = None

            def handle_response(resp):
                nonlocal pdf_blob, pdf_name
                if pdf_blob is not None:
                    return
                content_type = (resp.headers.get("content-type") or "").lower()
                if "pdf" not in content_type:
                    return
                try:
                    body = resp.body()
                except Exception as exc:  # pragma: no cover
                    res["notes"].append(f"resp_body_err:{exc}")
                    return
                if body[:4] == b"%PDF":
                    pdf_blob = body
                    cd = resp.headers.get("content-disposition") or ""
                    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, flags=re.I)
                    if m:
                        pdf_name = sanitize_filename(m.group(1))
                    else:
                        pdf_name = sanitize_filename(
                            os.path.basename(urlparse(resp.url).path) or ""
                        )

            context.on("response", handle_response)
            page = context.new_page()
            try:
                if verbose:
                    print(f"[yes_browser] navigate {url}")
                page.goto(url, wait_until="networkidle")
                try:
                    page.wait_for_function(
                        "() => { const el = document.querySelector('embed,iframe,object');"
                        " return el && el.src && el.src !== 'about:blank'; }",
                        timeout=5000,
                    )
                except playwright_timeout_error:
                    pass

                if pdf_blob is None:
                    locator = page.locator("embed, iframe, object")
                    count = locator.count()
                    for idx in range(count):
                        handle = locator.nth(idx)
                        src = (handle.get_attribute("src") or "").strip()
                        if not src or src == "about:blank":
                            continue
                        candidate_name = handle.get_attribute("name") or ""
                        blob: Optional[bytes] = None
                        if src.startswith("data:"):
                            blob = decode_data_url(src)
                        elif src.startswith("blob:"):
                            try:
                                arr = page.evaluate(
                                    """async (blobUrl) => {
                                        const resp = await fetch(blobUrl);
                                        const buf = await resp.arrayBuffer();
                                        return Array.from(new Uint8Array(buf));
                                    }""",
                                    src,
                                )
                                if arr:
                                    blob = bytes(arr)
                            except Exception as exc:  # pragma: no cover
                                res["notes"].append(f"blob_fetch_err:{exc}")
                        else:
                            try:
                                resp = context.request.get(src)
                                data = resp.body()
                                if data[:4] == b"%PDF":
                                    blob = data
                                    cd = resp.headers.get("content-disposition") or ""
                                    m = re.search(
                                        r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, flags=re.I
                                    )
                                    if m:
                                        candidate_name = m.group(1)
                            except Exception as exc:  # pragma: no cover
                                res["notes"].append(f"http_fetch_err:{exc}")
                        if blob:
                            pdf_blob = blob
                            pdf_name = sanitize_filename(candidate_name or os.path.basename(src))
                            break

                if pdf_blob:
                    res.update(
                        {"ok": True, "name": pdf_name or "yes_invoice.pdf", "blob": pdf_blob}
                    )
                else:
                    res["notes"].append("pdf_not_found")
            except Exception as exc:  # pragma: no cover - Playwright runtime
                res["notes"].append(f"browser_err:{exc}")
            finally:
                context.close()
                browser.close()
    except Exception as exc:  # pragma: no cover - Playwright runtime
        res["notes"].append(f"browser_init_err:{exc}")
    return res
