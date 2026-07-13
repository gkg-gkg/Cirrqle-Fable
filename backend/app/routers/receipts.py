"""Receipt / cashback-claim endpoints (Phase 4 + 5).

A receipt is a private photo proving a purchase for a deal. It doubles as a
cashback claim: it carries the deal's brand + £ amount (snapshotted at upload)
and a status (pending -> confirmed -> paid / rejected). The dashboard's money is
derived from these rows (see routers/account.py).

Reads/writes of a user's own receipts are auth'd; verify/reject and the review
list are admin-gated (reusing the campaigns admin key).
"""
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from ..db import get_session
from ..models import (AdminReceiptOut, Campaign, Receipt, ReceiptOut, User)
from ..security import get_current_user
from ..storage import (StorageError, StorageUploadError, receipt_view_url,
                       upload_receipt)
from .campaigns import require_admin

router = APIRouter(prefix="/receipts", tags=["receipts"])


def _earn_to_amount(earn: str) -> float:
    """'£13.00' -> 13.0 ; '£0.90' -> 0.9 ; '' -> 0.0."""
    nums = re.findall(r"[\d.]+", earn or "")
    try:
        return float(nums[0]) if nums else 0.0
    except ValueError:
        return 0.0


def _receipt_out(r: Receipt) -> ReceiptOut:
    return ReceiptOut(
        id=r.id, postId=r.post_id, campaignId=r.campaign_id,
        brand=r.brand, amount=r.amount, status=r.status, uploadedAt=r.uploaded_at,
    )


@router.get("", response_model=list[ReceiptOut])
def list_receipts(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """This user's receipts/claims (metadata only — no image URL)."""
    rows = session.exec(select(Receipt).where(Receipt.user_id == user.id)).all()
    return [_receipt_out(r) for r in rows]


@router.post("", response_model=ReceiptOut, status_code=201)
def create_receipt(
    post_id: str = Form(...),
    campaign_id: Optional[int] = Form(None),
    image: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Upload a receipt for one of this user's posts, tied to a deal.

    One receipt per (user, post): re-uploading replaces it and resets to pending.
    """
    if not post_id.strip():
        raise HTTPException(status_code=422, detail="post_id is required.")
    try:
        key = upload_receipt(image)
    except StorageUploadError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Snapshot the deal's brand + cashback amount so the claim is self-contained.
    brand, amount = "", 0.0
    if campaign_id is not None:
        camp = session.get(Campaign, campaign_id)
        if camp:
            brand = camp.brand
            amount = _earn_to_amount(camp.earn)

    existing = session.exec(
        select(Receipt).where(Receipt.user_id == user.id, Receipt.post_id == post_id)
    ).first()
    if existing:
        existing.image_key = key
        existing.campaign_id = campaign_id
        existing.brand = brand
        existing.amount = amount
        existing.status = "pending"
        existing.uploaded_at = datetime.now(timezone.utc)
        receipt = existing
    else:
        receipt = Receipt(
            user_id=user.id, post_id=post_id, campaign_id=campaign_id,
            brand=brand, amount=amount, image_key=key,
        )

    session.add(receipt)
    session.commit()
    session.refresh(receipt)
    return _receipt_out(receipt)


# ── Admin review (verify cashback claims) ──
@router.get("/admin", response_model=list[AdminReceiptOut],
            dependencies=[Depends(require_admin)])
def admin_list_receipts(
    status: Optional[str] = None,
    session: Session = Depends(get_session),
):
    """All receipts (optionally filtered by status), newest first, with a
    short-lived image URL for review."""
    query = select(Receipt, User).where(Receipt.user_id == User.id)
    if status:
        query = query.where(Receipt.status == status)
    rows = session.exec(query.order_by(Receipt.uploaded_at.desc())).all()
    return [
        AdminReceiptOut(
            id=r.id, userEmail=u.email, userName=f"{u.first_name} {u.last_name}",
            postId=r.post_id, brand=r.brand, amount=r.amount, status=r.status,
            uploadedAt=r.uploaded_at, imageUrl=receipt_view_url(r.image_key),
        )
        for r, u in rows
    ]


def _set_status(receipt_id: int, status: str, session: Session) -> ReceiptOut:
    r = session.get(Receipt, receipt_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    r.status = status
    session.add(r)
    session.commit()
    session.refresh(r)
    return _receipt_out(r)


@router.post("/{receipt_id}/verify", response_model=ReceiptOut,
             dependencies=[Depends(require_admin)])
def verify_receipt(receipt_id: int, session: Session = Depends(get_session)):
    """Admin: confirm a claim — its cashback becomes withdrawable."""
    return _set_status(receipt_id, "confirmed", session)


@router.post("/{receipt_id}/reject", response_model=ReceiptOut,
             dependencies=[Depends(require_admin)])
def reject_receipt(receipt_id: int, session: Session = Depends(get_session)):
    """Admin: reject a claim (no cashback)."""
    return _set_status(receipt_id, "rejected", session)
