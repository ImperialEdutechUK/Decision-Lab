"""Central configuration, loaded from environment / .env. Mirrors the Node backend's config.

No secrets live in the frontend; identity is proven by a signed launch/session token, never by
a raw query parameter.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv optional
    pass

BASE_DIR = Path(__file__).resolve().parent


def _bool(name, default=False):
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(name, default):
    try:
        return int(os.getenv(name, ""))
    except (TypeError, ValueError):
        return default


def _list(name):
    return [s.strip() for s in os.getenv(name, "").split(",") if s.strip()]


class Config:
    ENV = os.getenv("APP_ENV", "development")
    IS_PROD = ENV == "production"

    # Visible application name. Used for page titles, the top bar and the PDF header.
    APP_NAME = os.getenv("APP_NAME", "Decision Lab")

    # SQLite by default; set DATABASE_URL to a Postgres URL for production.
    # On Railway, DATABASE_URL is provided automatically when a Postgres plugin is attached.
    # It may arrive as a `postgres://...` URL - database/connection.py normalises it for SQLAlchemy.
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'decision_lab.db'}")

    # Optional libpq sslmode forced onto Postgres connections (e.g. "require" for the Railway
    # PUBLIC proxy URL used from your Windows machine). Leave blank to use whatever the URL carries.
    DB_SSLMODE = os.getenv("DB_SSLMODE", "")
    # Connection-pool tuning (safe defaults; pre-ping avoids stale connections after Railway sleeps).
    DB_POOL_SIZE = _int("DB_POOL_SIZE", 5)
    DB_MAX_OVERFLOW = _int("DB_MAX_OVERFLOW", 5)
    DB_POOL_RECYCLE = _int("DB_POOL_RECYCLE_SECONDS", 1800)

    # True when the process is running inside Railway (set in the Railway runtime). Used to refuse
    # a `*.railway.internal` host from a local machine, where that private host is unreachable.
    ON_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID")
                      or os.getenv("RAILWAY_SERVICE_ID") or os.getenv("RAILWAY_PRIVATE_DOMAIN"))

    # Signing secrets (HS256). Change in production.
    SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret-change-me")
    ADMIN_SECRET = os.getenv("ADMIN_SECRET", os.getenv("SESSION_SECRET", "dev-admin-secret-change-me"))
    LAUNCH_TOKEN_SECRET = os.getenv("LAUNCH_TOKEN_SECRET", "dev-launch-secret-change-me")

    SESSION_TTL_SECONDS = _int("SESSION_TTL_SECONDS", 28800)
    LAUNCH_TOKEN_MAX_AGE = _int("LAUNCH_TOKEN_MAX_AGE_SECONDS", 120)
    LAUNCH_TOKEN_ISSUER = os.getenv("LAUNCH_TOKEN_ISSUER", "https://lms.example.com")
    LAUNCH_TOKEN_AUDIENCE = os.getenv("LAUNCH_TOKEN_AUDIENCE", "decision-lab")

    # Admin bootstrap (used by tools/create_admin.py)
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

    # Dev mode: enables the sample-learner picker and the /?dev= launch. MUST be false in prod.
    DEV_MODE = _bool("DEV_MODE", not IS_PROD)

    # ── Learner identity (no learner login) ────────────────────────────────────
    # When the LMS cannot hand us a verified identity, offer a first-visit email-entry page.
    # The resulting identity is SELF-DECLARED and clearly marked unverified.
    ALLOW_EMAIL_IDENTITY = _bool("ALLOW_EMAIL_IDENTITY", True)
    EMAIL_IDENTITY_ISSUER = os.getenv("EMAIL_IDENTITY_ISSUER", "email://self-declared")
    EMAIL_VERIFIED_ISSUER = os.getenv("EMAIL_VERIFIED_ISSUER", "email://verified")
    # Optional one-time-code verification of the fallback email. Off by default (needs a mail
    # sender). When off, fallback identities stay self-declared/unverified by design.
    REQUIRE_EMAIL_VERIFICATION = _bool("REQUIRE_EMAIL_VERIFICATION", False)
    EMAIL_OTP_TTL_SECONDS = _int("EMAIL_OTP_TTL_SECONDS", 900)

    # ── Activity embedding / linking safety ────────────────────────────────────
    # Only these domains may be rendered inside an <iframe> (embedded activities). Anything else is
    # offered as an "open in a new tab" link instead. Never execute uploaded HTML/JS.
    EMBED_ALLOWED_DOMAINS = _list("EMBED_ALLOWED_DOMAINS") or [
        "h5p.com", "app.h5p.com", "www.youtube.com", "youtube.com", "youtu.be",
        "player.vimeo.com", "vimeo.com", "docs.google.com", "drive.google.com",
        "forms.office.com", "onedrive.live.com", "view.officeapps.live.com",
    ]
    # Optional allowlist for external (new-tab) activity links. Empty = allow any https URL.
    LINK_ALLOWED_DOMAINS = _list("LINK_ALLOWED_DOMAINS")

    # Where the companion (LTI/H5P) service is reachable, for embedding H5P in the learner UI.
    COMPANION_URL = os.getenv("COMPANION_URL", "")

    H5P_MAX_UPLOAD_BYTES = _int("H5P_MAX_UPLOAD_BYTES", 50 * 1024 * 1024)

    # General uploaded-file limit (activity documents, guide files, guideline files). Files are
    # stored in the database by default, which persists across redeploys on Railway PostgreSQL.
    MAX_UPLOAD_BYTES = _int("MAX_UPLOAD_BYTES", 25 * 1024 * 1024)
    # Allowed upload extensions (lowercase, no dot). Keep conservative; validated server-side.
    ALLOWED_UPLOAD_EXTENSIONS = _list("ALLOWED_UPLOAD_EXTENSIONS") or [
        "pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "csv", "txt",
        "zip", "html", "htm", "png", "jpg", "jpeg", "gif", "svg",
    ]

    # LTI 1.3 (companion service)
    LTI_ISSUER = os.getenv("LTI_PLATFORM_ISSUER", "")
    LTI_CLIENT_ID = os.getenv("LTI_CLIENT_ID", "")
    LTI_AUTH_LOGIN_URL = os.getenv("LTI_AUTH_LOGIN_URL", "")
    LTI_JWKS_URL = os.getenv("LTI_PLATFORM_JWKS_URL", "")
    LTI_DEPLOYMENT_ID = os.getenv("LTI_DEPLOYMENT_ID", "1")
    STREAMLIT_URL = os.getenv("STREAMLIT_URL", "http://localhost:8501")
    COMPANION_PUBLIC_URL = os.getenv("COMPANION_PUBLIC_URL", "http://localhost:8000")


config = Config()
