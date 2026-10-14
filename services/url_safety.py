"""URL validation + iframe domain allow-listing for externally hosted activities.

We only ever (a) open a validated https link in a new tab, or (b) embed an https URL whose host is
on the approved allowlist inside an <iframe>. We never execute uploaded HTML/JS or embed an
arbitrary origin, which is what keeps admin-managed activities safe.
"""
from urllib.parse import urlparse

from config import config


def host_of(url: str) -> str:
    try:
        return (urlparse((url or "").strip()).hostname or "").lower()
    except Exception:
        return ""


def _host_matches(host: str, allowed: list[str]) -> bool:
    host = (host or "").lower()
    for d in allowed:
        d = d.strip().lower().lstrip(".")
        if not d:
            continue
        if host == d or host.endswith("." + d):
            return True
    return False


def is_https(url: str) -> bool:
    try:
        return urlparse((url or "").strip()).scheme == "https"
    except Exception:
        return False


def is_allowed_embed(url: str) -> bool:
    """True only for an https URL whose host is on EMBED_ALLOWED_DOMAINS."""
    return is_https(url) and _host_matches(host_of(url), config.EMBED_ALLOWED_DOMAINS)


def is_allowed_link(url: str) -> bool:
    """True for an https URL; if LINK_ALLOWED_DOMAINS is set, host must match it too."""
    if not is_https(url):
        return False
    if not config.LINK_ALLOWED_DOMAINS:
        return True
    return _host_matches(host_of(url), config.LINK_ALLOWED_DOMAINS)


def validate_activity_urls(activity_type: str, url: str | None, embed_url: str | None,
                           open_mode: str) -> tuple[bool, str]:
    """Return (ok, message). Enforces https + the allowlists for the chosen open mode."""
    activity_type = (activity_type or "").upper()
    if activity_type in ("NATIVE", "H5P"):
        return True, "ok"  # uploaded packages carry no external URL

    # A DOCUMENT may be a file upload with no link; only validate a URL if one was supplied.
    if activity_type == "DOCUMENT" and not (url or embed_url):
        return True, "ok"

    if open_mode == "EMBED":
        target = embed_url or url
        if not target:
            return False, "An embed URL is required for an embedded activity."
        if not is_https(target):
            return False, "The embed URL must start with https://."
        if not is_allowed_embed(target):
            return False, (f"The embed host '{host_of(target)}' is not on the approved embed "
                           f"allowlist. Add it to EMBED_ALLOWED_DOMAINS or use 'Open in new tab'.")
        return True, "ok"

    # NEW_TAB link
    if not url:
        return False, "A launch URL is required for this activity."
    if not is_https(url):
        return False, "The launch URL must start with https://."
    if not is_allowed_link(url):
        return False, (f"The link host '{host_of(url)}' is not on LINK_ALLOWED_DOMAINS.")
    return True, "ok"
