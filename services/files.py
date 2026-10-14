"""Upload helpers: filename sanitisation, extension allow-listing and size limits.

Files are stored in the database (their bytes on the owning row), which persists across redeploys
on Railway PostgreSQL. Everything here validates server-side before anything is stored.
"""
import os
import re

from config import config

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")

# Extensions we can display inside the application (no download required).
INLINE_PDF = {"pdf"}
INLINE_IMAGE = {"png", "jpg", "jpeg", "gif", "svg", "webp"}
INLINE_TEXT = {"txt", "csv", "html", "htm"}


def sanitize_filename(name: str) -> str:
    """Return a safe, bare filename (no path, no traversal, bounded length)."""
    base = os.path.basename(str(name or "")).strip().replace("\\", "/").split("/")[-1]
    base = _SAFE.sub("_", base).strip("._") or "file"
    return base[:120]


def extension_of(name: str) -> str:
    i = (name or "").rfind(".")
    return (name[i + 1:].lower() if i >= 0 else "")


def validate_upload(name: str, data: bytes, *, allowed=None, max_bytes=None) -> tuple[bool, str]:
    """Return (ok, message). Enforces an extension allowlist and a maximum size."""
    allowed = {e.lower() for e in (allowed or config.ALLOWED_UPLOAD_EXTENSIONS)}
    max_bytes = max_bytes or config.MAX_UPLOAD_BYTES
    if not data:
        return False, "The file is empty."
    if len(data) > max_bytes:
        return False, f"The file is too large (limit {max_bytes // (1024 * 1024)} MB)."
    ext = extension_of(name)
    if ext not in allowed:
        return False, f"'.{ext}' files are not allowed. Allowed: {', '.join(sorted(allowed))}."
    return True, "ok"


def can_display_inline(name: str, mime: str = "") -> bool:
    ext = extension_of(name)
    return ext in (INLINE_PDF | INLINE_IMAGE | INLINE_TEXT) or (mime or "").startswith("image/")
