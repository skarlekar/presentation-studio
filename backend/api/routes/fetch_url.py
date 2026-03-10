"""URL content fetcher — extracts readable text from a web page for use as source material."""
import logging
from pydantic import BaseModel, HttpUrl

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


@router.post("/deck/fetch-url", response_model=FetchUrlResponse, tags=["deck"])
async def fetch_url(req: FetchUrlRequest) -> FetchUrlResponse:
    """Fetch readable text content from a URL.

    Uses trafilatura for article extraction, with an httpx fallback.
    Suitable for Medium articles, LinkedIn posts, blog posts, documentation, etc.

    Returns the extracted plain text and title, ready to paste into source_material.
    """
    url = req.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="URL must start with http:// or https://")

    try:
        import trafilatura
        import httpx

        # Rotate through user agents and try fallback URLs for paywalled sites
        UA_DESKTOP = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
        UA_GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

        base_headers = {
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Build list of (url, headers) attempts
        attempts: list[tuple[str, dict]] = [
            (url, {**base_headers, "User-Agent": UA_DESKTOP}),
            (url, {**base_headers, "User-Agent": UA_GOOGLEBOT}),
        ]

        # For Medium articles, try freedium.cfd proxy (publicly available bypass)
        if "medium.com" in url:
            freedium_url = "https://freedium.cfd/" + url.replace("https://", "").replace("http://", "")
            attempts.insert(1, (freedium_url, {**base_headers, "User-Agent": UA_DESKTOP}))

        html = None
        last_err = None
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            for attempt_url, attempt_headers in attempts:
                try:
                    response = await client.get(attempt_url, headers=attempt_headers)
                    if response.status_code < 400:
                        html = response.text
                        break
                    last_err = f"HTTP {response.status_code}"
                except httpx.RequestError as e:
                    last_err = type(e).__name__

        if not html:
            raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {last_err}")

        # trafilatura: best-in-class article/blog extraction
        result = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=False,
        )

        # Extract title separately
        meta = trafilatura.extract_metadata(html, default_url=url)
        title = meta.title if meta else None

        if not result or len(result.strip()) < 100:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not extract readable content from this URL. "
                    "The page may require login, use JavaScript rendering, "
                    "or contain no article-style text."
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
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch URL: HTTP {e.response.status_code}",
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch URL: {type(e).__name__}",
        )
    except Exception as e:
        logger.exception("Unexpected error fetching %s", url)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
