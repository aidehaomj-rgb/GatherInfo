"""Public document reader for HTML, rendered pages, PDFs and images."""
from __future__ import annotations

import asyncio
import io
import hashlib
import os
import shutil
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


@dataclass
class DocumentResult:
    url: str
    title: str = ""
    text: str = ""
    content_type: str = ""
    method: str = ""
    links: list[str] | None = None
    images: list[str] | None = None
    error: str | None = None
    artifacts: list[str] | None = None

    def to_dict(self):
        return asdict(self)


async def read_document(url: str, *, render: bool = False, follow_links: int = 0,
                        actions: list[dict] | None = None, find_text: str | None = None) -> dict:
    headers = {"User-Agent": "GatherInfoResearch/1.0 (+public-intelligence-research)"}
    try:
        async with httpx.AsyncClient(timeout=45, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
        kind = (response.headers.get("content-type") or "").lower()
        if "pdf" in kind or urlparse(url).path.lower().endswith(".pdf"):
            result = _read_pdf(url, response.content)
        elif kind.startswith("image/"):
            result = _read_image(url, response.content, kind)
        else:
            result = _read_html(url, response.text)
            if render or len(result.text) < 500:
                rendered = await _read_rendered(url, actions or [])
                if (render and rendered.method == "playwright") or len(rendered.text) > len(result.text):
                    result = rendered
        blocked_markers = ("access denied", "verify you are human", "captcha", "request blocked")
        if any(marker in f"{result.title} {result.text[:1000]}".casefold() for marker in blocked_markers):
            result.error = "Source blocked automated access; use an independent public source"
            result.method = "blocked"
        related = []
        for link in (result.links or [])[:max(0, follow_links)]:
            child = await read_document(link)
            if child.get("text"):
                related.append(child)
        payload = result.to_dict()
        if find_text:
            lines = str(result.text or "").splitlines()
            payload["matches"] = [line for line in lines if find_text.casefold() in line.casefold()][:50]
        payload["related_documents"] = related
        return payload
    except Exception as exc:
        return DocumentResult(url=url, method="failed", error=str(exc)).to_dict()


def _read_html(url: str, html: str) -> DocumentResult:
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for node in soup.select("script,style,noscript,nav,footer,form,aside"):
        node.decompose()
    root = soup.select_one("article,main,[role=main]") or soup.body or soup
    text = "\n".join(line.strip() for line in root.get_text("\n").splitlines() if line.strip())
    host = urlparse(url).netloc.casefold()
    links = []
    for anchor in root.select("a[href]"):
        href = urljoin(url, anchor.get("href", ""))
        if urlparse(href).scheme in {"http", "https"} and urlparse(href).netloc.casefold() == host:
            links.append(href.split("#", 1)[0])
    images = [urljoin(url, image.get("src", "")) for image in root.select("img[src]")]
    return DocumentResult(url=url, title=title, text=text[:100000], content_type="text/html", method="http_html", links=_unique(links)[:40], images=_unique(images)[:20])


async def _read_rendered(url: str, actions: list[dict]) -> DocumentResult:
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(1200)
            artifacts = []
            artifact_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "work", "research-artifacts"))
            os.makedirs(artifact_dir, exist_ok=True)
            for index, action in enumerate(actions[:12]):
                kind = action.get("type")
                selector = str(action.get("selector") or "")
                if kind == "click" and selector:
                    await page.locator(selector).first.click(timeout=10000)
                elif kind == "fill" and selector:
                    await page.locator(selector).first.fill(str(action.get("value") or ""), timeout=10000)
                elif kind == "press" and selector:
                    await page.locator(selector).first.press(str(action.get("key") or "Enter"), timeout=10000)
                elif kind == "wait":
                    await page.wait_for_timeout(min(10000, int(action.get("milliseconds") or 1000)))
                elif kind == "screenshot":
                    digest = hashlib.sha1(url.encode()).hexdigest()[:16]
                    path = os.path.join(artifact_dir, f"page-{digest}-{index}.png")
                    await page.screenshot(path=path, full_page=bool(action.get("full_page", True)))
                    artifacts.append(path)
                elif kind == "download" and selector:
                    async with page.expect_download(timeout=20000) as pending:
                        await page.locator(selector).first.click()
                    download = await pending.value
                    path = os.path.join(artifact_dir, download.suggested_filename)
                    await download.save_as(path); artifacts.append(path)
                await page.wait_for_timeout(500)
            result = _read_html(url, await page.content())
            result.method = "playwright"
            result.artifacts = artifacts
            await browser.close()
            return result
    except Exception as exc:
        return DocumentResult(url=url, method="playwright_failed", error=str(exc))


def _read_pdf(url: str, data: bytes) -> DocumentResult:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    method = "pypdf"
    if len(text.strip()) < 200 and _tesseract_path():
        import fitz
        document = fitz.open(stream=data, filetype="pdf")
        blocks = []
        for page in document[:20]:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            blocks.append(_ocr_bytes(pixmap.tobytes("png")))
        text = "\n\n".join(blocks)
        method = "pdf_ocr"
    title = str((reader.metadata or {}).get("/Title") or "")
    return DocumentResult(url=url, title=title, text=text[:150000], content_type="application/pdf", method=method)


def _read_image(url: str, data: bytes, kind: str) -> DocumentResult:
    if not _tesseract_path():
        return DocumentResult(url=url, content_type=kind, method="ocr_unavailable", error="Tesseract executable not installed")
    return DocumentResult(url=url, text=_ocr_bytes(data)[:50000], content_type=kind, method="tesseract")


def _ocr_bytes(data: bytes) -> str:
    from PIL import Image
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = _tesseract_path()
    try:
        return pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang=os.getenv("TESSERACT_LANG", "eng+chi_sim"))
    except pytesseract.TesseractError:
        return pytesseract.image_to_string(Image.open(io.BytesIO(data)), lang="eng")


def _tesseract_path() -> str | None:
    configured = os.getenv("TESSERACT_CMD", "").strip()
    if configured and os.path.isfile(configured):
        return configured
    return shutil.which("tesseract")


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
