"""First-visit EMAIL FALLBACK identity (used only when the LMS cannot hand us a verified learner).

Security posture (and honest limitations)
------------------------------------------
* This identity is **self-declared**. We mark it clearly as UNVERIFIED in the UI and in the admin
  reports by storing it under a distinct issuer (``config.EMAIL_IDENTITY_ISSUER``). It is NOT proof
  of who the person is - it only lets an un-launched visitor keep their own progress by email.
* We never trust an email supplied in the URL or an editable field as identity on its own: the
  email is only accepted through the first-visit POST form, and once accepted the learner is carried
  by the SIGNED, short-lived session token (``?s=``) - exactly like an LMS launch. Changing the
  email in the URL cannot surface another learner's record, because identity rides in the signed
  token, not the raw field.
* Optional one-time-code verification (``REQUIRE_EMAIL_VERIFICATION``) upgrades the identity to a
  verified issuer, but needs a real mail sender wired into ``send_login_code``. It is OFF by default.

The persistent learner record lives in PostgreSQL and is keyed by (issuer, email), so the same email
always maps back to the same history on any future visit.
"""
import re
import secrets
from datetime import datetime, timedelta

from config import config
from auth.passwords import hash_password, verify_password
from auth.learner_identity import upsert_learner
from database.connection import session_scope
from database.models import EmailOTP

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    e = normalize_email(email)
    return bool(e) and len(e) <= 254 and bool(_EMAIL_RE.match(e))


def claim_identity(email: str, verified: bool = False) -> dict:
    """Find-or-create the learner for a self-declared email and return the learner dict.
    Raises ValueError on a malformed email."""
    e = normalize_email(email)
    if not is_valid_email(e):
        raise ValueError("Please enter a valid email address.")
    issuer = config.EMAIL_VERIFIED_ISSUER if verified else config.EMAIL_IDENTITY_ISSUER
    local = e.split("@")[0]
    return upsert_learner({
        "issuer": issuer,
        "external_learner_id": e,       # keyed by email under this issuer
        "email": e,
        "display_name": local,
    })


def is_unverified_identity(learner: dict) -> bool:
    """True when the learner came from the self-declared email fallback (show an 'unverified' note)."""
    return bool(learner) and learner.get("issuer") == config.EMAIL_IDENTITY_ISSUER


# ── OPTIONAL one-time-code verification (off unless a mail sender is configured) ──────────────
def _hash_code(code: str) -> str:
    return hash_password(code)


def send_login_code(email: str) -> str | None:
    """Create and 'send' a 6-digit code. Returns the code ONLY in DEV_MODE (so you can test without
    a mail provider); in production wire a real sender here and return None.

    This is a scaffold: email delivery is intentionally not implemented, so verification is a no-op
    unless you plug in a mailer. We never claim an address is verified without a delivered code."""
    e = normalize_email(email)
    if not is_valid_email(e):
        raise ValueError("Please enter a valid email address.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    with session_scope() as s:
        s.add(EmailOTP(
            email=e, code_hash=_hash_code(code),
            expires_at=datetime.utcnow() + timedelta(seconds=config.EMAIL_OTP_TTL_SECONDS),
        ))
    # TODO: integrate a real email provider here, e.g. send `code` to `e`.
    return code if config.DEV_MODE else None


def verify_login_code(email: str, code: str) -> bool:
    e = normalize_email(email)
    now = datetime.utcnow()
    with session_scope() as s:
        rows = (
            s.query(EmailOTP)
            .filter(EmailOTP.email == e, EmailOTP.consumed_at.is_(None), EmailOTP.expires_at > now)
            .order_by(EmailOTP.created_at.desc())
            .all()
        )
        for row in rows:
            if verify_password(str(code).strip(), row.code_hash):
                row.consumed_at = now
                return True
    return False
