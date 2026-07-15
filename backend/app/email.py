"""Transactional email via AWS SES (Phase 6).

One small module the rest of the app calls to send mail. Two modes, mirroring
db.py / storage.py's "prod vs local" split:

  • SES_SENDER set   -> send through Amazon SES (boto3, imported lazily).
  • SES_SENDER unset -> no-op: log what WOULD have been sent and return False,
    so local dev and the test suite never deliver real email.

Every send is best-effort. `send_email` catches all errors and logs them — it
never raises — so a mail hiccup (SES down, address unverified in sandbox, bad
IAM) can't break the action that triggered it (a receipt upload, a withdrawal,
a login). Callers therefore never need their own try/except.

Each user-facing event has one small template below; they all funnel through
`send_email` for consistent branding.
"""
import logging
import os
from html import escape
from typing import Optional

logger = logging.getLogger("cirqle.email")

BRAND_COLOR = "#437D9E"   # Cirqle steel-blue (matches the site wordmark/favicon)


def _sender() -> Optional[str]:
    return os.environ.get("SES_SENDER") or None


def send_email(to: str, subject: str, html: str) -> bool:
    """Send one HTML email. Returns True if handed to SES, else False.

    Never raises: if SES_SENDER is unset it's a logged no-op; if the SES call
    fails the error is logged and swallowed.
    """
    sender = _sender()
    if not sender:
        logger.info("SES not configured (SES_SENDER unset); skipping email to %s: %r", to, subject)
        return False
    if not to:
        return False

    region = os.environ.get("AWS_REGION", "eu-west-2")
    try:
        import boto3  # imported lazily so local dev/tests need no boto3/AWS

        boto3.client("ses", region_name=region).send_email(
            Source=sender,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Html": {"Data": html, "Charset": "UTF-8"}},
            },
        )
        return True
    except Exception as exc:  # noqa: BLE001 — email is best-effort; never break the caller
        logger.warning("SES send to %s failed: %s", to, exc)
        return False


# ── Branding shell + small helpers ──
def _money(amount: float) -> str:
    return f"£{amount:,.2f}"


def _shell(heading: str, body_html: str, button: Optional[tuple[str, str]] = None) -> str:
    """Wrap body content in a minimal, inline-styled branded email shell.

    Email clients ignore <style>/external CSS, so everything is inline. `button`
    is an optional (label, url) call-to-action.
    """
    btn = ""
    if button:
        label, url = button
        btn = (
            f'<a href="{escape(url, quote=True)}" '
            f'style="display:inline-block;background:{BRAND_COLOR};color:#ffffff;'
            'text-decoration:none;font-weight:700;padding:13px 26px;border-radius:12px;'
            f'font-size:15px;margin:14px 0 4px;">{escape(label)}</a>'
        )
    return (
        '<!DOCTYPE html><html><body style="margin:0;background:#f4f6f8;'
        'font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1f2933;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#f4f6f8;padding:28px 16px;"><tr><td align="center">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:480px;background:#ffffff;border-radius:18px;overflow:hidden;'
        'border:1px solid #e6eaee;">'
        '<tr><td style="padding:26px 30px 6px;">'
        f'<div style="font-size:22px;font-weight:800;letter-spacing:-0.02em;color:{BRAND_COLOR};">cirqle</div>'
        '</td></tr>'
        '<tr><td style="padding:10px 30px 4px;">'
        f'<h1 style="margin:0 0 12px;font-size:20px;font-weight:800;color:#1f2933;">{escape(heading)}</h1>'
        f'<div style="font-size:15px;line-height:1.6;color:#3e4c59;">{body_html}{btn}</div>'
        '</td></tr>'
        '<tr><td style="padding:22px 30px 28px;">'
        '<div style="border-top:1px solid #eceff2;padding-top:16px;font-size:12px;'
        'line-height:1.6;color:#9aa5b1;">You\'re receiving this because you have a Cirqle '
        'account. If this wasn\'t you, you can safely ignore this email.</div>'
        '</td></tr></table></td></tr></table></body></html>'
    )


# ── One template per event ──
def send_login_code(to: str, code: str) -> bool:
    html = _shell(
        "Your sign-in code",
        "<p style='margin:0 0 14px;'>Use this code to finish signing in. "
        "It expires in 10 minutes.</p>"
        f"<div style='font-size:32px;font-weight:800;letter-spacing:8px;color:#1f2933;"
        f"background:#f0f4f8;border-radius:12px;padding:16px;text-align:center;'>{escape(code)}</div>",
    )
    return send_email(to, f"{code} is your Cirqle sign-in code", html)


def send_password_reset(to: str, reset_url: str) -> bool:
    html = _shell(
        "Reset your password",
        "<p style='margin:0;'>Tap the button below to choose a new password. This link "
        "expires in 30 minutes. If you didn't ask to reset your password, ignore this email.</p>",
        button=("Reset password", reset_url),
    )
    return send_email(to, "Reset your Cirqle password", html)


def send_receipt_received(to: str, name: str, brand: str) -> bool:
    html = _shell(
        "Receipt received",
        f"<p style='margin:0;'>Hi {escape(name)}, thanks — we've received your "
        f"{escape(brand) or 'cashback'} receipt and we're reviewing your claim. "
        "We'll email you as soon as it's confirmed.</p>",
    )
    return send_email(to, "Receipt received — we're reviewing your claim", html)


def send_cashback_confirmed(to: str, name: str, brand: str, amount: float) -> bool:
    html = _shell(
        "Cashback confirmed",
        f"<p style='margin:0;'>Great news {escape(name)} — your {escape(brand)} claim is "
        f"confirmed and <strong>{_money(amount)}</strong> has been added to your Cirqle "
        "wallet, ready to withdraw.</p>",
    )
    return send_email(to, f"Cashback confirmed — {_money(amount)} added to your wallet", html)


def send_receipt_rejected(to: str, name: str, brand: str) -> bool:
    html = _shell(
        "Update on your claim",
        f"<p style='margin:0;'>Hi {escape(name)}, we've reviewed your {escape(brand) or 'cashback'} "
        "claim and unfortunately we couldn't approve it this time. This is usually because the "
        "receipt or the tagged post didn't meet the deal's terms — you're welcome to try again.</p>",
    )
    return send_email(to, "An update on your Cirqle claim", html)


def send_cashback_paid(to: str, name: str, amount: float) -> bool:
    html = _shell(
        "Cashback paid out",
        f"<p style='margin:0;'>Hi {escape(name)}, your withdrawal of "
        f"<strong>{_money(amount)}</strong> is on its way. Thanks for being part of Cirqle!</p>",
    )
    return send_email(to, f"Cashback paid out — {_money(amount)}", html)
