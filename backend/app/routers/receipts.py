"""Receipt endpoints (Phase 4).

A receipt is a private photo a user uploads to prove a purchase for one of their
tagged Instagram posts. The image goes to PRIVATE storage (storage.upload_receipt)
and only metadata is kept in the DB / returned to the browser — never the image
itself, since receipts are personal.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from ..db import get_session
from ..models import Receipt, ReceiptOut, User
from ..security import get_current_user
from ..storage import StorageError, StorageUploadError, upload_receipt

router = APIRouter(prefix="/receipts", tags=["receipts"])


def _receipt_out(r: Receipt) -> ReceiptOut:
    return ReceiptOut(id=r.id, postId=r.post_id, status=r.status, uploadedAt=r.uploaded_at)


@router.get("", response_model=list[ReceiptOut])
def list_receipts(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """This user's receipts (metadata only — no image URLs). Feeds feed.html."""
    rows = session.exec(select(Receipt).where(Receipt.user_id == user.id)).all()
    return [_receipt_out(r) for r in rows]


@router.post("", response_model=ReceiptOut, status_code=201)
def create_receipt(
    post_id: str = Form(...),
    image: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Upload a receipt image for one of this user's posts.

    One receipt per (user, post): re-uploading replaces the stored image.
    """
    if not post_id.strip():
        raise HTTPException(status_code=422, detail="post_id is required.")
    try:
        key = upload_receipt(image)
    except StorageUploadError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    existing = session.exec(
        select(Receipt).where(Receipt.user_id == user.id, Receipt.post_id == post_id)
    ).first()
    if existing:
        existing.image_key = key
        existing.status = "received"
        existing.uploaded_at = datetime.now(timezone.utc)
        receipt = existing
    else:
        receipt = Receipt(user_id=user.id, post_id=post_id, image_key=key)

    session.add(receipt)
    session.commit()
    session.refresh(receipt)
    return _receipt_out(receipt)
