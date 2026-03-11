"""URL content fetcher — extracts readable text from a web page for use as source material."""
import logging
import re
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()


class FetchUrlRequest(BaseModel):
    url: str  # plain str so we can return a clean error message


class FetchUrlResponse(BaseModel):
    url: str
    title: str | None
    content: str
    char_count: int


def _extract_medium_rss_handle(url: str) -> str | None:
    """Extract the Medium username/publication RSS feed URL from an article URL.

    Handles both:
      - skarlekar.medium.com/article-slug
      - medium.com/@skarlekar/article-slug
    """
    # subdomain form: skarlekar.medium.com/...
    m = re.match(r"https?://([^.]+)\.medium\.com", url)
    if m:
        username = m.group(1)
        if username not in ("www", "cdn-images"):
            return f"https://medium.com/feed/@{username}"

    # path form: medium.com/@username/...
    m = re.match(r"https?://(?:www\.)?medium\.com/@([^/?#]+)", url)
    if m:
        return f"https://medium.com/feed/@{m.group(1)}"

    return None


def _extract_post_id_from_url(url: str) -> str | None:
    """Extract the 12-char hex post ID from a Medium URL slug."""
    # Medium slugs end with a hex ID like -be42af8e291a
    m = re.search(r"-([0-9a-f]{12})(?:[/?#]|$)", url)
    return m.group(1) if m else None


async def _fetch_medium_via_rss(url: str) -> tuple[str | None, str | None]:
    """Try to fetch a Medium article's text from the author's RSS feed.

    Returns (title, content) or (None, None) if not found.
    """
    import httpx
    from html.parser import HTMLParser

    rss_url = _extract_medium_rss_handle(url)
    if not rss_url:
        return None, None

    post_id = _extract_post_id_from_url(url)

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DeckStudio/1.0)",
        "Accept": "application/rss+xml, application/xml, text/xml",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            resp = await client.get(rss_url, headers=headers)
            if resp.status_code >= 400:
                return None, None
            rss_text = resp.text
    except Exception as e:
        logger.warning("RSS fetch error for %s: %s", rss_url, e)
        return None, None

    # Parse items from RSS — find the one matching our URL or post_id
    items = re.findall(r"<item>(.*?)</item>", rss_text, re.DOTALL)
    for item in items:
        item_link = re.search(r"<link>(.*?)</link>", item)
        item_guid = re.search(r"<guid[^>]*>(.*?)</guid>", item)

        link_val = item_link.group(1).strip() if item_link else ""
        guid_val = item_guid.group(1).strip() if item_guid else ""

        # Match by post_id in guid (e.g. https://medium.com/p/be42af8e291a)
        matched = False
        if post_id and post_id in guid_val:
            matched = True
        elif post_id and post_id in link_val:
            matched = True
        elif url.split("?")[0].rstrip("/") in link_val:
            matched = True

        if not matched:
            continue

        # Extract title
        title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", item, re.DOTALL)
        title = title_m.group(1).strip() if title_m else None

        # Extract content — prefer content:encoded (full HTML)
        content_m = re.search(
            r"<content:encoded><!\[CDATA\[(.*?)\]\]></content:encoded>", item, re.DOTALL
        )
        if not content_m:
            content_m = re.search(
                r"<description><!\[CDATA\[(.*?)\]\]></description>", item, re.DOTALL
            )

        if not content_m:
            continue

        html_content = content_m.group(1)

        # Strip HTML tags to plain text
        class _StripHTML(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts: list[str] = []
                self._skip_tags = {"script", "style", "img"}
                self._current_skip = False

            def handle_starttag(self, tag, attrs):
                if tag in self._skip_tags:
                    self._current_skip = True
                if tag in ("p", "h1", "h2", "h3", "h4", "li", "br"):
                    self.parts.append("\n")

            def handle_endtag(self, tag):
                if tag in self._skip_tags:
                    self._current_skip = False
                if tag in ("p", "h1", "h2", "h3", "h4", "li"):
                    self.parts.append("\n")

            def handle_data(self, data):
                if not self._current_skip:
                    self.parts.append(data)

            def get_text(self):
                return re.sub(r"\n{3,}", "\n\n", "".join(self.parts)).strip()

        parser = _StripHTML()
        parser.feed(html_content)
        plain = parser.get_text()

        if len(plain) >= 200:
            return title, plain

    return None, None


@router.post("/deck/fetch-url", response_model=FetchUrlResponse, tags=["deck"])
async def fetch_url(req: FetchUrlRequest) -> FetchUrlResponse:
    """Fetch readable text content from a URL.

    Supports:
    - Medium articles (via RSS feed — no paywall / 403 issues)
    - General web pages via trafilatura + httpx with multiple user-agent fallbacks

    Returns the extracted plain text and title, ready to paste into source_material.
    """
    url = req.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="URL must start with http:// or https://")

    try:
        import trafilatura
        import httpx

        # ── Medium: use RSS feed (most reliable, no 403) ──────────────────────
        if "medium.com" in url:
            title, content = await _fetch_medium_via_rss(url)
            if content and len(content) >= 200:
                logger.info("Medium RSS fetch: %d chars, title: %s", len(content), title)
                return FetchUrlResponse(
                    url=url,
                    title=title,
                    content=content,
                    char_count=len(content),
                )
            # Fall through to direct fetch if RSS didn't work

        # ── General: direct fetch with user-agent rotation ────────────────────
        UA_DESKTOP = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
        UA_GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

        base_headers = {
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        }

        attempts: list[tuple[str, dict]] = [
            (url, {**base_headers, "User-Agent": UA_DESKTOP}),
            (url, {**base_headers, "User-Agent": UA_GOOGLEBOT}),
        ]

        html = None
        last_err = "Unknown error"
        last_status = None
        async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as client:
            for attempt_url, attempt_headers in attempts:
                try:
                    response = await client.get(attempt_url, headers=attempt_headers)
                    logger.info("Fetch %s -> HTTP %d", attempt_url, response.status_code)
                    if response.status_code < 400:
                        html = response.text
                        break
                    last_err = f"HTTP {response.status_code}"
                    last_status = response.status_code
                except httpx.RequestError as e:
                    last_err = type(e).__name__

        if not html:
            hint = ""
            if last_status in (401, 403):
                hint = (
                    " This page blocks automated access. "
                    "Try copying the text manually and pasting into Source Material."
                )
            raise HTTPException(
                status_code=502,
                detail=f"Could not retrieve page: {last_err}.{hint}",
            )

        result = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=False,
        )
        meta = trafilatura.extract_metadata(html, default_url=url)
        title = meta.title if meta else None

        if not result or len(result.strip()) < 100:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not extract readable content. "
                    "The page may require login or JavaScript rendering. "
                    "Try pasting the text manually into Source Material."
                ),
            )

        content = result.strip()
        logger.info("Fetched %d chars from %s", len(content), url)
        return FetchUrlResponse(
            url=url,
            title=title,
            content=content,
            char_count=len(content),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error fetching %s", url)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
