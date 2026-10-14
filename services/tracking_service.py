"""Generic, persistent activity tracking for NON-native activities (external links, embeds,
videos, documents, H5P links).

Design principles (matching the brief)
---------------------------------------
* Everything is written to PostgreSQL (never only to Streamlit session state or the browser).
* We record only what we genuinely observe ourselves - ACCESS, LAUNCH, VIEW - plus timestamps and
  counts. These are NOT scores.
* A real score / completion is stored **only** when a trusted integration supplies it
  (xAPI from the companion today; LTI 1.3 AGS later). Those calls set ``verified=True`` and
  ``score_verified`` on the rollup. A plain link/iframe can never set a verified score.
* One durable ``ActivityProgress`` row per (learner, activity): returning or refreshing updates it
  in place (no duplicate rows). The ``ActivityEvent`` log is append-only history.

Native missions (I12/I14) and uploaded .h5p packages keep using MissionAttempt via
``services/progress_service.py``; this module complements that for the new activity types.
"""
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from database.connection import session_scope
from database.models import Activity, ActivityEvent, ActivityProgress, Learner


# Activity types whose score/completion we can obtain only through a trusted integration.
# For these we are explicit in the UI that only launch/access is observed unless configured.
UNVERIFIED_BY_DEFAULT = {"H5P_LINK", "EXTERNAL_QUIZ", "EMBED", "VIDEO", "DOCUMENT", "LINK"}


def _coerce_activity(s, activity_id=None, code=None, track=None):
    """Resolve an Activity row from id, or (code, track). Returns the row or None."""
    if activity_id:
        a = s.query(Activity).filter_by(id=activity_id).one_or_none()
        if a:
            return a
    if code and track:
        return s.query(Activity).filter_by(code=code, track=track).one_or_none()
    return None


def _get_or_create_progress(s, learner_id, activity):
    row = (
        s.query(ActivityProgress)
        .filter_by(learner_id=learner_id, activity_id=activity.id)
        .one_or_none()
    )
    if row is None:
        row = ActivityProgress(
            learner_id=learner_id, activity_id=activity.id,
            code=activity.code, track=activity.track,
            completion_status="NOT_STARTED",
        )
        s.add(row)
        try:
            s.flush()
        except IntegrityError:
            # A concurrent request created it first - re-read and use that one.
            s.rollback()
            row = (
                s.query(ActivityProgress)
                .filter_by(learner_id=learner_id, activity_id=activity.id)
                .one()
            )
    return row


def _add_event(s, learner_id, activity, event_type, source="UI", score=None, max_score=None,
               success=None, verified=False, detail=None):
    s.add(ActivityEvent(
        learner_id=learner_id,
        activity_id=activity.id if activity else None,
        code=activity.code if activity else (detail or {}).get("code"),
        track=activity.track if activity else (detail or {}).get("track"),
        event_type=event_type, source=source, score=score, max_score=max_score,
        success=success, verified=verified, detail=detail,
    ))


# ── observed-only events (never a score) ───────────────────────────────────────
def touch_access(learner_id, activity_id=None, code=None, track=None, source="UI"):
    """First/continuing access to an activity. Upserts progress and logs an ACCESS event.
    Call this once per open (the UI guards against Streamlit reruns)."""
    now = datetime.utcnow()
    with session_scope() as s:
        activity = _coerce_activity(s, activity_id, code, track)
        if not activity:
            return None
        p = _get_or_create_progress(s, learner_id, activity)
        if p.first_access_at is None:
            p.first_access_at = now
        p.last_access_at = now
        p.view_count = (p.view_count or 0) + 1
        if p.completion_status in (None, "NOT_STARTED"):
            p.completion_status = "ACCESSED"
        _add_event(s, learner_id, activity, "ACCESS", source=source)
        return p.id


def record_launch(learner_id, activity_id=None, code=None, track=None, source="UI", detail=None):
    """The learner launched/opened the external activity. Observed only - not a score/completion."""
    now = datetime.utcnow()
    with session_scope() as s:
        activity = _coerce_activity(s, activity_id, code, track)
        if not activity:
            return None
        p = _get_or_create_progress(s, learner_id, activity)
        if p.first_access_at is None:
            p.first_access_at = now
        p.last_access_at = now
        p.launch_count = (p.launch_count or 0) + 1
        p.attempt_count = (p.attempt_count or 0) + 1
        if p.completion_status in (None, "NOT_STARTED", "ACCESSED"):
            p.completion_status = "IN_PROGRESS"
        _add_event(s, learner_id, activity, "LAUNCH", source=source, detail=detail)
        return p.id


def record_error(learner_id, activity_id=None, code=None, track=None, message="", source="UI"):
    with session_scope() as s:
        activity = _coerce_activity(s, activity_id, code, track)
        _add_event(s, learner_id, activity, "ERROR", source=source, detail={"message": str(message)[:500]})


# ── verified results (ONLY from a trusted integration) ─────────────────────────
def record_verified_result(learner_id, activity_id=None, code=None, track=None, *,
                           score=None, max_score=None, success=None, completed=False,
                           progress_pct=None, source="XAPI", detail=None):
    """Store a REAL score/completion supplied by a trusted integration (xAPI / LTI-AGS).
    Sets score_verified=True. Never call this for a plain launch/access."""
    now = datetime.utcnow()
    with session_scope() as s:
        activity = _coerce_activity(s, activity_id, code, track)
        if not activity:
            return None
        p = _get_or_create_progress(s, learner_id, activity)
        p.last_access_at = now
        if score is not None:
            if p.best_score is None or (max_score and score / max_score >= (p.best_score / (p.best_max_score or max_score))):
                p.best_score = int(score)
                p.best_max_score = int(max_score) if max_score else p.best_max_score
            p.score_verified = True
        if progress_pct is not None:
            p.progress_pct = int(progress_pct)
        if success is not None:
            p.passed = bool(success)
        if completed:
            p.completion_status = "COMPLETED"
            p.completed_at = p.completed_at or now
        elif p.completion_status in (None, "NOT_STARTED", "ACCESSED"):
            p.completion_status = "IN_PROGRESS"
        _add_event(s, learner_id, activity, "SCORE" if score is not None else "COMPLETE",
                   source=source, score=score, max_score=max_score, success=success,
                   verified=True, detail=detail)
        return p.id


# ── reads ───────────────────────────────────────────────────────────────────
def _prog_dict(p: ActivityProgress) -> dict:
    return {
        "activity_id": p.activity_id, "code": p.code, "track": p.track,
        "completion_status": p.completion_status, "launch_count": p.launch_count,
        "view_count": p.view_count, "attempt_count": p.attempt_count,
        "best_score": p.best_score, "best_max_score": p.best_max_score,
        "progress_pct": p.progress_pct, "passed": p.passed, "score_verified": p.score_verified,
        "first_access_at": p.first_access_at, "last_access_at": p.last_access_at,
        "completed_at": p.completed_at,
    }


def progress_for_learner(learner_id) -> dict:
    """{activity_id: progress_dict} for every non-native activity this learner has touched."""
    with session_scope() as s:
        rows = s.query(ActivityProgress).filter_by(learner_id=learner_id).all()
        return {p.activity_id: _prog_dict(p) for p in rows}


def progress_one(learner_id, activity_id) -> dict | None:
    with session_scope() as s:
        p = s.query(ActivityProgress).filter_by(learner_id=learner_id, activity_id=activity_id).one_or_none()
        return _prog_dict(p) if p else None
