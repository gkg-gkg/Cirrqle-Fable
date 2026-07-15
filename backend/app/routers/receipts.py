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
from ..email import (send_cashback_confirmed, send_receipt_received,
                     send_receipt_rejected)
from ..models import (AdminReceiptOut, Campaign, Mention, Receipt, ReceiptOut,
                      User)
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


def _receipt_out(r: Receipt, with_image: bool = False) -> ReceiptOut:
    return ReceiptOut(
        id=r.id, postId=r.post_id, campaignId=r.campaign_id,
        brand=r.brand, amount=r.amount, status=r.status, uploadedAt=r.uploaded_at,
        imageUrl=receipt_view_url(r.image_key) if with_image else None,
    )


def _post_tags_brand(caption: Optional[str], brand: str) -> bool:
    """Does the post's caption tag the brand? ("Nike" matches 'nike' or '@nike';
    multi-word brands match with spaces dropped, e.g. 'Pure Gym' -> '@puregym')."""
    if not caption or not brand:
        return False
    cap = caption.lower()
    handle = brand.lower().replace(" ", "")
    return brand.lower() in cap or handle in cap.replace(" ", "")


@router.get("", response_model=list[ReceiptOut])
def list_receipts(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """This user's receipts/claims, each with a short-lived URL to view their
    own receipt image (presigned; None in local mode)."""
    rows = session.exec(select(Receipt).where(Receipt.user_id == user.id)).all()
    return [_receipt_out(r, with_image=True) for r in rows]


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

    # Auto-verify: if the user's tagged post for this claim mentions the brand,
    # confirm instantly — no manual admin review needed.
    status = "pending"
    if brand:
        mention = session.get(Mention, post_id)
        if mention and mention.user_id == user.id and _post_tags_brand(mention.caption, brand):
            status = "confirmed"

    existing = session.exec(
        select(Receipt).where(Receipt.user_id == user.id, Receipt.post_id == post_id)
    ).first()
    if existing:
        existing.image_key = key
        existing.campaign_id = campaign_id
        existing.brand = brand
        existing.amount = amount
        existing.status = status
        existing.uploaded_at = datetime.now(timezone.utc)
        receipt = existing
    else:
        receipt = Receipt(
            user_id=user.id, post_id=post_id, campaign_id=campaign_id,
            brand=brand, amount=amount, image_key=key, status=status,
        )

    session.add(receipt)
    session.commit()
    session.refresh(receipt)

    # Best-effort email — send_email swallows any failure so it never blocks the
    # upload. Auto-confirmed claims skip straight to the "confirmed" message.
    if receipt.status == "confirmed":
        send_cashback_confirmed(user.email, user.first_name, receipt.brand, receipt.amount)
    else:
        send_receipt_received(user.email, user.first_name, receipt.brand)

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


def _set_status(receipt_id: int, status: str, session: Session) -> Receipt:
    r = session.get(Receipt, receipt_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    r.status = status
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


def _notify_status_change(r: Receipt, session: Session) -> None:
    """Email the claim's owner about a confirm/reject. Best-effort (send_email
    swallows failures), so it never breaks the admin action."""
    user = session.get(User, r.user_id)
    if user is None:
        return
    if r.status == "confirmed":
        send_cashback_confirmed(user.email, user.first_name, r.brand, r.amount)
    elif r.status == "rejected":
        send_receipt_rejected(user.email, user.first_name, r.brand)


@router.post("/{receipt_id}/verify", response_model=ReceiptOut,
             dependencies=[Depends(require_admin)])
def verify_receipt(receipt_id: int, session: Session = Depends(get_session)):
    """Admin: confirm a claim — its cashback becomes withdrawable."""
    r = _set_status(receipt_id, "confirmed", session)
    _notify_status_change(r, session)
    return _receipt_out(r)


@router.post("/{receipt_id}/reject", response_model=ReceiptOut,
             dependencies=[Depends(require_admin)])
def reject_receipt(receipt_id: int, session: Session = Depends(get_session)):
    """Admin: reject a claim (no cashback)."""
    r = _set_status(receipt_id, "rejected", session)
    _notify_status_change(r, session)
    return _receipt_out(r)
