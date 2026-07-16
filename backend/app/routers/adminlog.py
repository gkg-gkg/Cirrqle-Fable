"""Admin activity log endpoint (Phase 6).

A read-only feed of recent admin actions, shown at the bottom of admin.html.
Admin-gated (reuses the campaigns X-Admin-Key).
"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import AdminActivity, AdminActivityOut
from .campaigns import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/activity", response_model=list[AdminActivityOut],
            dependencies=[Depends(require_admin)])
def list_activity(limit: int = Query(default=100, ge=1, le=500),
                  session: Session = Depends(get_session)):
    """Recent admin actions, newest first."""
    rows = session.exec(
        select(AdminActivity).order_by(AdminActivity.id.desc()).limit(limit)
    ).all()
    return [
        AdminActivityOut(id=a.id, action=a.action, detail=a.detail, createdAt=a.created_at)
        for a in rows
    ]
