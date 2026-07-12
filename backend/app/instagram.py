"""Server-side Instagram scraping via Apify.

The Apify token lives here (read from the APIFY_TOKEN environment variable) and
NEVER reaches the browser — that is the whole point of Phase 2. The frontend
asks our API to refresh; our API does the scrape and returns only the finished
posts.

We scrape the *brand* account's mentions (posts that tag @cirqle.ltd) and let
the caller filter down to a single user's own posts.
"""
import os
import time

from apify_client import ApifyClient

# apify/instagram-scraper — same actor the old client-side code used.
ACTOR_ID = "apify/instagram-scraper"

# Instagram account whose mentions we scrape. Override with CIRQLE_BRAND_HANDLE.
BRAND_HANDLE = os.environ.get("CIRQLE_BRAND_HANDLE", "cirqle.ltd")

# Every user's feed is filtered from the SAME brand-wide scrape, so a burst of
# refreshes would otherwise fire many identical ~1-min Apify runs. Cache the raw
# scrape for a short window and reuse it. (In-memory: fine for our single server
# process; move to Redis if we ever run multiple workers.)
_CACHE_TTL_SECONDS = 60
_cache: dict = {"at": 0.0, "limit": None, "posts": None}


class ScrapeError(RuntimeError):
    """Raised when we cannot complete a scrape (missing token or Apify failure)."""


def _do_scrape(token: str, limit: int) -> list[dict]:
    """The actual Apify run — no caching. Raises ScrapeError on failure."""
    client = ApifyClient(token)
    run_input = {
        "directUrls": [f"https://www.instagram.com/{BRAND_HANDLE}/"],
        "resultsType": "mentions",   # posts where the brand is tagged
        "resultsLimit": limit,
    }
    try:
        # .call() starts the run and blocks until it finishes (~1 min).
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        dataset = client.dataset(run["defaultDatasetId"])
        return list(dataset.iterate_items())
    except Exception as exc:  # noqa: BLE001 — surface any Apify failure as one type
        raise ScrapeError(f"Instagram scrape failed: {exc}") from exc


def scrape_brand_mentions(limit: int = 50) -> list[dict]:
    """Return posts that tag the brand account, reusing a recent scrape if fresh.

    Raises ScrapeError if the token is missing or the Apify run fails.
    """
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        raise ScrapeError("Server is missing APIFY_TOKEN — set it in the backend .env.")

    fresh = (
        _cache["posts"] is not None
        and _cache["limit"] == limit
        and (time.time() - _cache["at"]) < _CACHE_TTL_SECONDS
    )
    if fresh:
        return _cache["posts"]

    posts = _do_scrape(token, limit)
    _cache.update(at=time.time(), limit=limit, posts=posts)
    return posts
