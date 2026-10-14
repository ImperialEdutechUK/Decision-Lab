"""Signed tokens (HS256 via PyJWT).

- session token: minted after a validated launch/dev-login and carried in the Streamlit URL
  (?s=<jwt>) so identity survives a browser refresh WITHOUT trusting a raw parameter - the token
  is signed and short-lived, so it cannot be forged or edited by the learner.
- launch token: the signed, single-use token an LMS (or the LTI companion) issues to hand the
  learner to this app. Verified here; the nonce/jti single-use check is enforced by the caller.
"""
import time
import jwt

from config import config

_ALG = "HS256"


# ── learner session token ─────────────────────────────────────────────────────
def issue_session(learner_id: str, ttl: int | None = None) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": learner_id, "typ": "learner", "iat": now, "exp": now + (ttl or config.SESSION_TTL_SECONDS)},
        config.SESSION_SECRET, algorithm=_ALG,
    )


def verify_session(token: str) -> str | None:
    try:
        payload = jwt.decode(token, config.SESSION_SECRET, algorithms=[_ALG])
        if payload.get("typ") != "learner":
            return None
        return payload.get("sub")
    except Exception:
        return None


# ── admin session token ───────────────────────────────────────────────────────
def issue_admin_session(admin_id: str, ttl: int | None = None) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": admin_id, "typ": "admin", "iat": now, "exp": now + (ttl or config.SESSION_TTL_SECONDS)},
        config.ADMIN_SECRET, algorithm=_ALG,
    )


def verify_admin_session(token: str) -> str | None:
    try:
        payload = jwt.decode(token, config.ADMIN_SECRET, algorithms=[_ALG])
        if payload.get("typ") != "admin":
            return None
        return payload.get("sub")
    except Exception:
        return None


# ── LMS launch token (fallback mechanism / companion output) ──────────────────
def verify_launch_token(token: str) -> dict | None:
    """Verify a signed launch token. Returns normalized claims or None.
    Expected claims: iss, aud, sub, jti, iat, optional email/given_name/family_name/name/mission.
    """
    try:
        payload = jwt.decode(
            token,
            config.LAUNCH_TOKEN_SECRET,
            algorithms=[_ALG],
            audience=config.LAUNCH_TOKEN_AUDIENCE,
            issuer=config.LAUNCH_TOKEN_ISSUER,
            options={"require": ["exp", "iat"] if False else []},
        )
    except Exception:
        # try without exp if the token used max-age style; enforce max age below
        try:
            payload = jwt.decode(token, config.LAUNCH_TOKEN_SECRET, algorithms=[_ALG],
                                 audience=config.LAUNCH_TOKEN_AUDIENCE, issuer=config.LAUNCH_TOKEN_ISSUER)
        except Exception:
            return None
    iat = payload.get("iat")
    if iat and (int(time.time()) - int(iat)) > config.LAUNCH_TOKEN_MAX_AGE:
        return None
    if not payload.get("sub") or not payload.get("jti"):
        return None
    return {
        "issuer": payload.get("iss"),
        "external_learner_id": payload.get("sub"),
        "jti": payload.get("jti"),
        "email": payload.get("email"),
        "first_name": payload.get("given_name"),
        "last_name": payload.get("family_name"),
        "display_name": payload.get("name"),
        "mission": payload.get("mission"),
    }


def mint_launch_token(sub, email=None, name=None, jti=None, mission=None, given_name=None, family_name=None):
    """Helper used by the companion and by tests to create a valid launch token."""
    import uuid
    now = int(time.time())
    claims = {
        "iss": config.LAUNCH_TOKEN_ISSUER,
        "aud": config.LAUNCH_TOKEN_AUDIENCE,
        "sub": sub,
        "jti": jti or uuid.uuid4().hex,
        "iat": now,
        "exp": now + config.LAUNCH_TOKEN_MAX_AGE,
    }
    if email:
        claims["email"] = email
    if name:
        claims["name"] = name
    if given_name:
        claims["given_name"] = given_name
    if family_name:
        claims["family_name"] = family_name
    if mission:
        claims["mission"] = mission
    return jwt.encode(claims, config.LAUNCH_TOKEN_SECRET, algorithm=_ALG)
