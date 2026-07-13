"""Account dashboard endpoints (Phase 5).

Real per-user numbers for the "My Account" page, all derived from the user's
receipts (the cashback ledger) + their stored posts. No placeholders.
"""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..db import get_session
from ..models import AccountStats, ActivityItem, Mention, Receipt, User
from ..security import get_current_user

router = APIRouter(prefix="/account", tags=["account"])


def _compute_stats(user: User, session: Session) -> AccountStats:
    receipts = session.exec(select(Receipt).where(Receipt.user_id == user.id)).all()

    def total(*statuses) -> float:
        return round(sum(r.amount for r in receipts if r.status in statuses), 2)

    pending = total("pending")
    wallet = total("confirmed")          # confirmed = available to withdraw
    paid = total("paid")
    earned = round(wallet + paid, 2)     # all verified cashback ever

    posts = session.exec(select(Mention).where(Mention.user_id == user.id)).all()
    brands = {r.brand for r in receipts if r.brand}
    recent = sorted(receipts, key=lambda r: r.uploaded_at, reverse=True)[:6]

    return AccountStats(
        totalEarned=earned,
        pending=pending,
        wallet=wallet,
        paidOut=paid,
        brandsUsed=len(brands),
        postsCount=len(posts),
        receiptsCount=len(receipts),
        activity=[
            ActivityItem(brand=r.brand or "Cashback", amount=r.amount,
                         status=r.status, date=r.uploaded_at)
            for r in recent
        ],
    )


@router.get("/stats", response_model=AccountStats)
def get_stats(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """The user's real dashboard figures."""
    return _compute_stats(user, session)


@router.post("/withdraw", response_model=AccountStats)
def withdraw(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Withdraw the confirmed balance — marks confirmed claims as paid."""
    confirmed = session.exec(
        select(Receipt).where(Receipt.user_id == user.id, Receipt.status == "confirmed")
    ).all()
    for r in confirmed:
        r.status = "paid"
        session.add(r)
    session.commit()
    return _compute_stats(user, session)
