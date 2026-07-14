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


class MerchantApplication(SQLModel, table=True):
    """A brand's partnership application, submitted from contact.html.

    Public (no user account needed) — merchants aren't Cirqle users. The admin
    reviews these on admin.html and, on approve, a live `Campaign` is created
    from the key fields (`campaign_id` links to it). Lifecycle:
      pending -> approved (deal published)  or  rejected.
    `goals` holds a JSON-encoded list[str] as TEXT (same trick as Campaign.tags).
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    brand: str = ""
    website: str = ""
    category: str = ""
    cashback_rate: float = 0          # target cashback %, becomes the deal rate
    markets: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    role: str = ""
    revenue: str = ""
    orders: str = ""
    aov: str = ""                     # avg order value (£), kept as text (may be blank)
    budget: str = ""
    timeline: str = ""
    goals: str = "[]"                 # JSON-encoded list[str]
    heard: str = ""
    message: str = ""
    status: str = "pending"           # pending -> approved / rejected
    campaign_id: Optional[int] = Field(default=None, foreign_key="campaign.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None


class Receipt(SQLModel, table=True):
    """A cashback claim: a receipt a user uploaded for a deal (Phase 4 + 5).

    Per-user data keyed by `user_id` (like Mention). Doubles as the cashback
    ledger — every £ figure on the dashboard is derived from these rows, so no
    separate transactions table is needed. Lifecycle:
      pending (uploaded) -> confirmed (admin-verified) -> paid (withdrawn);  or rejected.
    `brand`/`amount` are snapshotted from the deal at upload so the claim stays
    correct even if the campaign is later edited. `image_key` is a private storage
    key (never a public URL, never returned to the owner's browser).
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    post_id: str = Field(index=True)                 # the Instagram post it proves
    campaign_id: Optional[int] = Field(default=None, foreign_key="campaign.id")
    brand: str = ""                                  # snapshot of the deal's brand
    amount: float = 0                                # cashback £ (snapshot of deal.earn)
    image_key: str                                   # private storage key
    status: str = "pending"                          # pending -> confirmed -> paid / rejected
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
    # (send just what you want to update; omitted fields are left untouched).
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[EmailStr] = None
    instagramHandle: Optional[str] = None


class PasswordChangeIn(BaseModel):
    currentPassword: str
    newPassword: str


# ── What the API returns (never includes the password hash) ──
class UserOut(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    instagramHandle: str
    createdAt: Optional[datetime] = None


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


# ── Receipts / cashback (Phase 4 + 5) ──
# The owner never gets an image URL (receipts are private) — just the claim's
# brand, amount and status.
class ReceiptOut(BaseModel):
    id: int
    postId: str
    campaignId: Optional[int] = None
    brand: str
    amount: float
    status: str
    uploadedAt: datetime


class AdminReceiptOut(BaseModel):
    """Admin review view — includes who submitted it + a short-lived image URL."""
    id: int
    userEmail: str
    userName: str
    postId: str
    brand: str
    amount: float
    status: str
    uploadedAt: datetime
    imageUrl: Optional[str] = None   # presigned GET, expires shortly


class ActivityItem(BaseModel):
    brand: str
    amount: float
    status: str
    date: datetime


class AccountStats(BaseModel):
    """Real per-user dashboard numbers, all derived from the user's receipts."""
    totalEarned: float   # confirmed + paid
    pending: float       # awaiting verification
    wallet: float        # confirmed, available to withdraw
    paidOut: float       # already withdrawn
    brandsUsed: int
    postsCount: int
    receiptsCount: int
    activity: list[ActivityItem]


# ── Merchant partnership applications ──
class MerchantApplicationIn(BaseModel):
    """What contact.html's partnership form sends. The key fields needed to
    publish a deal on approval are required; the rest is optional context."""
    brand: str
    website: str
    category: str
    cashbackRate: float
    firstName: str
    lastName: str
    email: EmailStr
    markets: str = ""
    phone: str = ""
    role: str = ""
    revenue: str = ""
    orders: str = ""
    aov: str = ""
    budget: str = ""
    timeline: str = ""
    goals: list[str] = []
    heard: str = ""
    message: str = ""


class MerchantApplicationOut(BaseModel):
    """The admin review view — the full application plus its status."""
    id: int
    brand: str
    website: str
    category: str
    cashbackRate: float
    markets: str
    firstName: str
    lastName: str
    email: str
    phone: str
    role: str
    revenue: str
    orders: str
    aov: str
    budget: str
    timeline: str
    goals: list[str]
    heard: str
    message: str
    status: str
    campaignId: Optional[int] = None
    createdAt: datetime
