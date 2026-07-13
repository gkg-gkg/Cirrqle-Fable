"""Database tables and the request/response shapes for the API.

`User` (table=True) is a real database table. The other classes are just the
JSON shapes we accept and return — kept separate so we never leak the password
hash to the browser.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    first_name: str
    last_name: str
    email: str = Field(index=True, unique=True)
    password_hash: str
    instagram_handle: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Mention(SQLModel, table=True):
    """One Instagram post that tags the brand, owned by one user.

    PK is the Instagram post id (a post has a single owner, so it maps to one
    user). `user_id` links it back to its owner — the standard "one table per
    kind of user data, keyed by user_id" pattern.
    """
    id: str = Field(primary_key=True)                    # Instagram post id
    user_id: int = Field(index=True, foreign_key="user.id")
    url: Optional[str] = None
    display_url: Optional[str] = None
    caption: Optional[str] = None
    timestamp: Optional[str] = None
    owner_username: Optional[str] = None
    owner_full_name: Optional[str] = None
    likes_count: Optional[int] = None
    comments_count: Optional[int] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class Campaign(SQLModel, table=True):
    """A cashback deal shown to everyone — the global catalog (Phase 3).

    Unlike `Mention` this is NOT keyed by user; it's shared content authored
    through the admin form. `tags` and `images` hold JSON-encoded lists as TEXT
    so the shape is identical on SQLite and Postgres (no DB-specific JSON type).
    Columns are the union of what `deal.html` and `browse.html` render.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    brand: str = ""
    title: str = ""            # long detail title (deal.html hero)
    card_title: str = ""       # short listing title (browse card)
    card_desc: str = ""        # short listing description (browse card)
    long_desc: str = ""        # deal.html desc2
    emoji: str = ""            # fallback thumbnail when no images yet
    category: str = ""
    rate: float = 0            # cashback %
    earn: str = ""             # e.g. "£13.00"
    spend_desc: str = ""       # deal.html desc, e.g. "on a £100 spend"
    total_paid: str = ""       # e.g. "£112,705 paid to members"
    members: str = ""          # e.g. "1.8k"
    claims: int = 0            # browse "claims" count
    expiry: str = ""           # "30 Jun 2026" / "Ongoing" / "New members only"
    location: str = ""         # e.g. "Online · UK"
    terms: str = ""            # HTML string
    brand_url: str = ""        # outbound shop link
    bg: str = "var(--paper-deep)"
    tags: str = "[]"           # JSON-encoded list[str]
    images: str = "[]"         # JSON-encoded list[str] of image URLs
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Receipt(SQLModel, table=True):
    """A purchase receipt a user uploaded for one of their tagged posts (Phase 4).

    Per-user data keyed by `user_id` (same pattern as Mention). `post_id` links
    it to the Instagram post it proves. `image_key` is an OPAQUE private storage
    key (S3 object key or local filename) — receipts are private, so we store the
    key, never a public URL, and never return it to the browser.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    post_id: str = Field(index=True)      # the Instagram post this receipt is for
    image_key: str                        # private storage key (not web-served)
    status: str = "received"
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


# ── What the browser sends ──
class SignupIn(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    password: str
    instagramHandle: str


class SigninIn(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdateIn(BaseModel):
    # Only fields the user is allowed to change. Optional -> PATCH semantics
    # (send just what you want to update).
    instagramHandle: Optional[str] = None


# ── What the API returns (never includes the password hash) ──
class UserOut(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    instagramHandle: str


class AuthOut(BaseModel):
    token: str
    user: UserOut


# ── Instagram feed (Phase 2) ──
# A trimmed post shape: only the fields the feed page renders, so we never leak
# the rest of the raw scrape to the browser.
class FeedPost(BaseModel):
    id: Optional[str] = None
    url: Optional[str] = None
    displayUrl: Optional[str] = None
    caption: Optional[str] = None
    timestamp: Optional[str] = None
    ownerUsername: Optional[str] = None
    ownerFullName: Optional[str] = None
    likesCount: Optional[int] = None
    commentsCount: Optional[int] = None


class FeedRefreshOut(BaseModel):
    posts: list[FeedPost]
    updated: Optional[datetime] = None   # None when the user has no stored posts yet


# ── Campaigns (Phase 3) ──
class CampaignIn(BaseModel):
    """The text fields the admin form sends (as a JSON payload alongside the
    uploaded image files). Every field is optional so PATCH can send a partial
    update — the router only applies the fields that were actually provided.
    """
    brand: Optional[str] = None
    title: Optional[str] = None
    cardTitle: Optional[str] = None
    cardDesc: Optional[str] = None
    longDesc: Optional[str] = None
    emoji: Optional[str] = None
    category: Optional[str] = None
    rate: Optional[float] = None
    earn: Optional[str] = None
    spendDesc: Optional[str] = None
    totalPaid: Optional[str] = None
    members: Optional[str] = None
    claims: Optional[int] = None
    expiry: Optional[str] = None
    location: Optional[str] = None
    terms: Optional[str] = None
    brandUrl: Optional[str] = None
    bg: Optional[str] = None
    tags: Optional[list[str]] = None


class CampaignOut(BaseModel):
    id: int
    brand: str
    title: str
    cardTitle: str
    cardDesc: str
    longDesc: str
    emoji: str
    category: str
    rate: float
    earn: str
    spendDesc: str
    totalPaid: str
    members: str
    claims: int
    expiry: str
    location: str
    terms: str
    brandUrl: str
    bg: str
    tags: list[str]
    images: list[str]


# ── Receipts (Phase 4) ──
# No image URL is returned — receipts are private; the browser only needs to know
# which posts have a receipt and its status.
class ReceiptOut(BaseModel):
    id: int
    postId: str
    status: str
    uploadedAt: datetime
