"""Cashback clearing rules — time-based confirmation.

A claim's cashback is NOT confirmed the moment a receipt is reviewed. Instead it
"clears" automatically CONFIRM_DAYS after the Instagram post's date — matching the
countdown the feed already shows. So:

  • upload a receipt for a post  -> the claim is 'pending' (clearing)
  • CONFIRM_DAYS after the POST date -> it auto-becomes 'confirmed' (in the wallet)
  • admin can 'reject' a claim within the window; a withdrawn claim is 'paid'

We compute the effective status on read (no background job, no stored 'confirmed'
for new claims), so a claim flips to confirmed on its own once the 3 days pass.
Legacy rows already stored as 'confirmed' are kept as-is.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from .models import Receipt

CONFIRM_DAYS = 3


def _naive_utc(dt: datetime) -> datetime:
    """Drop tzinfo (converting to UTC first) so we can compare against utcnow()."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def parse_post_ts(ts: Optional[str]) -> Optional[datetime]:
    """Parse an Instagram post timestamp (ISO 8601, possibly 'Z') to naive UTC."""
    if not ts:
        return None
    try:
        return _naive_utc(datetime.fromisoformat(ts.replace("Z", "+00:00")))
    except (ValueError, TypeError):
        return None


def clears_at(receipt: Receipt, post_ts: Optional[datetime]) -> datetime:
    """When this claim's cashback clears: CONFIRM_DAYS after the post date, or the
    upload date if the post date is unknown."""
    return _naive_utc(post_ts or receipt.uploaded_at) + timedelta(days=CONFIRM_DAYS)


def effective_status(receipt: Receipt, post_ts: Optional[datetime]) -> str:
    """The claim's real status right now. 'pending' claims clear to 'confirmed'
    once CONFIRM_DAYS have passed since the post date; any other stored status
    (legacy 'confirmed' / 'paid' / 'rejected') is returned unchanged."""
    if receipt.status != "pending":
        return receipt.status
    if datetime.utcnow() >= clears_at(receipt, post_ts):
        return "confirmed"
    return "pending"
