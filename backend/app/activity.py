"""Admin activity log helper.

Records admin actions (approve/reject applications + campaign submissions,
verify/reject receipt claims, create merchant logins, reply to merchants) so
admin.html can show a scrollable feed of what's been done.
"""
from sqlmodel import Session

from .models import AdminActivity


def log_activity(session: Session, action: str, detail: str = "") -> None:
    """Record one admin action. Call after the action has committed successfully.

    Best-effort: never raises, so a logging hiccup can't break the admin action."""
    try:
        session.add(AdminActivity(action=action, detail=(detail or "")[:500]))
        session.commit()
    except Exception:  # noqa: BLE001 — logging is best-effort
        session.rollback()
