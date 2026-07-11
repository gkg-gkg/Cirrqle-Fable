"""Instagram feed endpoint (Phase 2).

`POST /feed/refresh` scrapes the brand's Instagram mentions server-side (using
the server's Apify token) and returns only the posts belonging to the signed-in
user. The browser never sees the token, and each user only sees their own posts.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..instagram import ScrapeError, scrape_brand_mentions
from ..models import FeedPost, FeedRefreshOut, User
from ..security import get_current_user

router = APIRouter(prefix="/feed", tags=["feed"])


def _to_feed_post(raw: dict) -> FeedPost:
    """Keep only the fields the feed page renders."""
    return FeedPost(
        id=raw.get("id"),
        url=raw.get("url"),
        displayUrl=raw.get("displayUrl"),
        caption=raw.get("caption"),
        timestamp=raw.get("timestamp"),
        ownerUsername=raw.get("ownerUsername"),
        ownerFullName=raw.get("ownerFullName"),
        likesCount=raw.get("likesCount"),
        commentsCount=raw.get("commentsCount"),
    )


@router.post("/refresh", response_model=FeedRefreshOut)
def refresh(user: User = Depends(get_current_user)):
    """Scrape brand mentions and return this user's own tagged posts."""
    handle = (user.instagram_handle or "").strip().lstrip("@").lower()
    if not handle:
        raise HTTPException(
            status_code=400,
            detail="No Instagram handle on your account. Add one to see your posts.",
        )

    try:
        raw_posts = scrape_brand_mentions(limit=50)
    except ScrapeError as exc:
        # 503: the scrape (an upstream dependency) is unavailable/misconfigured.
        raise HTTPException(status_code=503, detail=str(exc))

    mine = [
        _to_feed_post(p)
        for p in raw_posts
        if (p.get("ownerUsername") or "").lower() == handle
    ]
    return FeedRefreshOut(posts=mine, updated=datetime.now(timezone.utc))
