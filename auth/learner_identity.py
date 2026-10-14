"""Resolve (find-or-create) a Learner from validated launch claims, and consume launch nonces.
Identity key is (issuer, external_learner_id) - never a browser-supplied value.
"""
from datetime import datetime, timedelta

from database.connection import session_scope
from database.models import Learner, LearnerProgress, LaunchNonce


def upsert_learner(claims: dict):
    issuer = claims.get("issuer")
    ext = claims.get("external_learner_id")
    if not issuer or not ext:
        raise ValueError("launch claims missing issuer/external_learner_id")

    name = (
        claims.get("display_name")
        or " ".join(x for x in [claims.get("first_name"), claims.get("last_name")] if x).strip()
        or (claims.get("email").split("@")[0] if claims.get("email") else None)
    )

    with session_scope() as s:
        learner = (
            s.query(Learner)
            .filter(Learner.issuer == issuer, Learner.external_learner_id == ext)
            .one_or_none()
        )
        if learner is None:
            learner = Learner(
                issuer=issuer, external_learner_id=ext,
                email=claims.get("email"), first_name=claims.get("first_name"),
                last_name=claims.get("last_name"), display_name=name,
            )
            s.add(learner)
            s.flush()
            s.add(LearnerProgress(learner_id=learner.id))
        else:
            if claims.get("email"):
                learner.email = claims["email"]
            if name:
                learner.display_name = name
            if claims.get("first_name"):
                learner.first_name = claims["first_name"]
            if claims.get("last_name"):
                learner.last_name = claims["last_name"]
            learner.last_accessed_at = datetime.utcnow()
            if s.query(LearnerProgress).filter_by(learner_id=learner.id).one_or_none() is None:
                s.add(LearnerProgress(learner_id=learner.id))
        s.flush()
        return {
            "id": learner.id, "email": learner.email, "display_name": learner.display_name,
            "first_name": learner.first_name, "last_name": learner.last_name,
            "issuer": learner.issuer, "external_learner_id": learner.external_learner_id,
        }


def consume_nonce(jti: str, issuer: str) -> bool:
    """Register and consume a launch jti exactly once. Returns True if it was fresh."""
    with session_scope() as s:
        existing = s.query(LaunchNonce).filter_by(nonce=jti).one_or_none()
        if existing is not None:
            return False
        s.add(LaunchNonce(nonce=jti, issuer=issuer or "", expires_at=datetime.utcnow() + timedelta(minutes=10), used_at=datetime.utcnow()))
        return True


def get_learner(learner_id: str):
    with session_scope() as s:
        l = s.query(Learner).filter_by(id=learner_id).one_or_none()
        if not l:
            return None
        return {
            "id": l.id, "email": l.email, "display_name": l.display_name,
            "first_name": l.first_name, "last_name": l.last_name,
            "issuer": l.issuer, "external_learner_id": l.external_learner_id,
        }
