"""Progress engine for admin-managed activities.

Two storage paths, by activity type:

* Uploaded H5P packages (type H5P) are played in-app and tracked per attempt in ``MissionAttempt``
  (+ ``DecisionEvent``), with real score/completion written only from xAPI via the companion.
* All other types (H5P links, external quizzes, embeds, videos, documents, links) are tracked in
  ``ActivityProgress`` (launch/access, plus a verified score only when a trusted integration
  supplies one). See ``services/tracking_service.py``.

Learner-facing reads only ever return PUBLISHED activities. Every read/write is scoped to one
learner. There are no built-in activities.
"""
from datetime import datetime

from database.connection import session_scope
from database.models import (
    MissionAttempt, DecisionEvent, LearnerProgress, Learner, Activity, H5PVersion, ActivityProgress,
)
from content.registry import TRACK_CODES, TRACKS

# Activity types tracked per-attempt via MissionAttempt. Everything else uses ActivityProgress.
_ATTEMPT_TYPES = ("H5P",)


def _is_published(a: Activity) -> bool:
    return bool(a.available) and (a.status or "").upper() == "PUBLISHED"


# ── rollup helpers ──────────────────────────────────────────────────────────────
def _best_by_activity(s, learner_id):
    rows = (
        s.query(MissionAttempt)
        .filter_by(learner_id=learner_id)
        .order_by(MissionAttempt.score.desc(), MissionAttempt.completed.desc(),
                  MissionAttempt.last_accessed_at.desc())
        .all()
    )
    best = {}
    for r in rows:
        k = f"{r.mission_id}:{r.level}"
        if k not in best:
            best[k] = r
    return best


def _status_of(a):
    if a is None:
        return "NOT_STARTED"
    return a.status or ("COMPLETED" if a.completed else "IN_PROGRESS")


# ── per-activity learner status (PUBLISHED activities only) ──────────────────────
def activities_with_status(learner_id):
    """{track: [activity_row, ...]} for PUBLISHED activities, with the learner's status per row."""
    with session_scope() as s:
        best = _best_by_activity(s, learner_id)
        ext = {p.activity_id: p for p in s.query(ActivityProgress).filter_by(learner_id=learner_id).all()}
        out = {}
        for code in TRACK_CODES:
            acts = (
                s.query(Activity)
                .filter(Activity.track == code, Activity.available == True)  # noqa: E712
                .order_by(Activity.order_index)
                .all()
            )
            acts = [a for a in acts if _is_published(a)]
            rows = []
            for act in acts:
                atype = act.activity_type or act.kind or "LINK"
                row = {
                    "id": act.id, "code": act.code, "title": act.title, "description": act.description,
                    "est_minutes": act.est_minutes, "kind": act.kind, "activity_type": atype,
                    "available": act.available, "url": act.url, "embed_url": act.embed_url,
                    "open_mode": act.open_mode, "instructions": act.instructions,
                    "category": act.category, "provider": act.provider,
                    "pass_mark": act.pass_mark, "due_date": act.due_date,
                    "status": "NOT_STARTED", "score": None, "max_score": None, "percentage": None,
                    "attempts": 0, "score_verified": None, "last_accessed_at": None,
                }
                if atype in _ATTEMPT_TYPES:
                    a = best.get(f"{act.code}:{code}")
                    row.update(
                        status=_status_of(a),
                        score=a.score if a else None, max_score=a.max_score if a else None,
                        percentage=a.percentage if a else None,
                        attempts=a.attempt_number if a else 0,
                        score_verified=True if (a and a.completed) else None,
                        last_accessed_at=a.last_accessed_at if a else None,
                    )
                else:
                    p = ext.get(act.id)
                    if p:
                        row.update(
                            status=p.completion_status or "NOT_STARTED",
                            score=p.best_score, max_score=p.best_max_score,
                            percentage=p.progress_pct, attempts=p.attempt_count,
                            score_verified=bool(p.score_verified),
                            last_accessed_at=p.last_access_at,
                        )
                rows.append(row)
            out[code] = rows
        return out


# ── dashboards ────────────────────────────────────────────────────────────────
def track_progress(learner_id):
    """Per-course summary for the two track cards, derived from published activities."""
    status = activities_with_status(learner_id)
    out = {}
    for code in TRACK_CODES:
        rows = status.get(code, [])
        available = len(rows)
        attempted = completed = points = max_points = score_sum = scored = 0
        last = None
        for r in rows:
            if r["status"] and r["status"] != "NOT_STARTED":
                attempted += 1
            if r["status"] == "COMPLETED":
                completed += 1
            if r["score_verified"] and r["score"] is not None:
                points += r["score"]
                if r["max_score"] is not None:
                    max_points += r["max_score"]
                score_sum += r["score"]
                scored += 1
            at = r["last_accessed_at"]
            if at and (last is None or at > last["at"]):
                last = {"code": r["code"], "title": r["title"], "at": at}
        out[code] = {
            "code": code, "name": TRACKS[code]["name"],
            "activities_available": available, "activities_total": available,
            "attempted": attempted, "completed": completed,
            "completion_pct": round(completed / available * 100) if available else 0,
            "best_points": points, "max_points": max_points,
            "average_score": round(score_sum / scored, 2) if scored else None,
            "last_activity": ({"code": last["code"], "title": last["title"]} if last else None),
        }
    return out


def recompute_progress(learner_id):
    """Refresh the LearnerProgress rollup from current activity status. Called after an H5P
    completion; also safe to call any time."""
    status = activities_with_status(learner_id)
    attempted = completed = points = 0
    for code in TRACK_CODES:
        for r in status.get(code, []):
            if r["status"] and r["status"] != "NOT_STARTED":
                attempted += 1
            if r["status"] == "COMPLETED":
                completed += 1
            if r["score_verified"] and r["score"] is not None:
                points += r["score"]
    with session_scope() as s:
        prog = s.query(LearnerProgress).filter_by(learner_id=learner_id).one_or_none()
        if prog is None:
            prog = LearnerProgress(learner_id=learner_id)
            s.add(prog)
        prog.completed_missions = completed
        prog.attempted_missions = attempted
        prog.total_points = points
    return {"completed_missions": completed, "attempted_missions": attempted, "total_points": points}


def recently_opened(learner_id, limit=8):
    """Most-recently touched activities across H5P attempts and external progress (published only)."""
    with session_scope() as s:
        acts = {(a.code, a.track): a for a in s.query(Activity).all()}
        items = {}
        for a in (s.query(MissionAttempt).filter_by(learner_id=learner_id)
                  .order_by(MissionAttempt.last_accessed_at.desc()).limit(40).all()):
            key = (a.mission_id, a.level)
            act = acts.get(key)
            if not act or not _is_published(act):
                continue
            cur = items.get(key)
            if cur is None or (a.last_accessed_at and a.last_accessed_at > cur["last_accessed_at"]):
                items[key] = {
                    "code": a.mission_id, "track": a.level, "title": act.title,
                    "activity_type": act.activity_type,
                    "status": a.status or ("COMPLETED" if a.completed else "IN_PROGRESS"),
                    "score": a.score, "max_score": a.max_score,
                    "score_verified": bool(a.completed), "last_accessed_at": a.last_accessed_at,
                }
        for p in (s.query(ActivityProgress).filter_by(learner_id=learner_id)
                  .order_by(ActivityProgress.last_access_at.desc()).limit(40).all()):
            key = (p.code, p.track)
            act = acts.get(key)
            if not act or not _is_published(act):
                continue
            cur = items.get(key)
            ts = p.last_access_at
            if cur is None or (ts and cur["last_accessed_at"] and ts > cur["last_accessed_at"]):
                items[key] = {
                    "code": p.code, "track": p.track, "title": act.title,
                    "activity_type": act.activity_type,
                    "status": p.completion_status, "score": p.best_score, "max_score": p.best_max_score,
                    "score_verified": bool(p.score_verified), "last_accessed_at": ts,
                }
        ordered = sorted(items.values(), key=lambda r: (r["last_accessed_at"] or datetime.min), reverse=True)
        return ordered[:limit]


def activity_detail(learner_id, code, track):
    """Detail for one PUBLISHED activity, with the learner's record. Returns None if not found or
    not published (learners never see unpublished content)."""
    with session_scope() as s:
        act = s.query(Activity).filter_by(code=code, track=track).one_or_none()
        if not act or not _is_published(act):
            return None
        atype = act.activity_type or act.kind or "LINK"
        best = None
        if atype in _ATTEMPT_TYPES:
            attempts = (
                s.query(MissionAttempt)
                .filter_by(learner_id=learner_id, mission_id=code, level=track)
                .order_by(MissionAttempt.attempt_number.asc())
                .all()
            )
            if attempts:
                b = sorted(attempts, key=lambda a: (a.score, int(a.completed)), reverse=True)[0]
                best = {
                    "score": b.score, "max_score": b.max_score, "percentage": b.percentage,
                    "status": _status_of(b), "completed": b.completed,
                    "attempt_number": b.attempt_number,
                }
        ext = None
        if atype not in _ATTEMPT_TYPES:
            p = s.query(ActivityProgress).filter_by(learner_id=learner_id, activity_id=act.id).one_or_none()
            if p:
                ext = {
                    "completion_status": p.completion_status, "launch_count": p.launch_count,
                    "view_count": p.view_count, "attempt_count": p.attempt_count,
                    "best_score": p.best_score, "best_max_score": p.best_max_score,
                    "progress_pct": p.progress_pct, "passed": p.passed,
                    "score_verified": bool(p.score_verified),
                    "first_access_at": p.first_access_at, "last_access_at": p.last_access_at,
                    "completed_at": p.completed_at,
                }
        return {
            "activity": {
                "id": act.id, "code": act.code, "title": act.title, "description": act.description,
                "est_minutes": act.est_minutes, "kind": act.kind,
                "activity_type": atype, "track": track, "available": act.available,
                "url": act.url, "embed_url": act.embed_url, "open_mode": act.open_mode,
                "provider": act.provider, "instructions": act.instructions, "category": act.category,
                "pass_mark": act.pass_mark, "max_points": act.max_points, "due_date": act.due_date,
                "has_guideline_file": bool(act.guideline_file_bytes),
                "guideline_file_name": act.guideline_file_name,
            },
            "external": ext,
            "best": best,
        }


def practice_record(learner_id):
    """Formative practice record: per-course rollup plus recently completed activities."""
    with session_scope() as s:
        learner = s.query(Learner).filter_by(id=learner_id).one_or_none()
        act_titles = {(a.code, a.track): a.title for a in s.query(Activity).all()}
    status = activities_with_status(learner_id)
    tracks = {}
    for code in TRACK_CODES:
        rows = status.get(code, [])
        available = len(rows)
        attempted = completed = total = max_sum = score_sum = scored = 0
        for r in rows:
            if r["status"] and r["status"] != "NOT_STARTED":
                attempted += 1
            if r["status"] == "COMPLETED":
                completed += 1
            if r["score_verified"] and r["score"] is not None:
                total += r["score"]
                if r["max_score"] is not None:
                    max_sum += r["max_score"]
                score_sum += r["score"]
                scored += 1
        tracks[code] = {
            "name": TRACKS[code]["name"], "attempted": attempted, "completed": completed,
            "total_practice_score": total, "max_practice_score": max_sum,
            "average_score": round(score_sum / scored, 2) if scored else None,
            "completion_pct": round(completed / available * 100) if available else 0,
        }

    recent = []
    for code in TRACK_CODES:
        for r in status.get(code, []):
            if r["status"] == "COMPLETED":
                sc = (f'{r["score"]}/{r["max_score"]}' if (r["score"] is not None and r["max_score"] is not None)
                      else (str(r["score"]) if r["score"] is not None else "-"))
                recent.append({
                    "activity": r["code"],
                    "title": act_titles.get((r["code"], code), r["title"]),
                    "track": code, "score": sc,
                    "last_accessed_at": r["last_accessed_at"],
                })
    recent.sort(key=lambda x: (x["last_accessed_at"] or datetime.min), reverse=True)
    return {
        "title": "Practice Record",
        "learner": {"name": (learner.display_name or learner.email) if learner else "Learner",
                    "email": learner.email if learner else None},
        "generated_at": datetime.utcnow(),
        "tracks": tracks, "recent": recent[:12],
    }


# ── H5P attempts (uploaded packages, played in-app via the companion) ────────────
def h5p_start(learner_id, code, level):
    with session_scope() as s:
        act = s.query(Activity).filter_by(code=code, track=level).one_or_none()
        if not act or act.kind != "H5P":
            raise ValueError("not_h5p_activity")
        version = (
            s.query(H5PVersion).filter_by(activity_id=act.id, status="PUBLISHED")
            .order_by(H5PVersion.version.desc()).first()
        )
        if not version:
            raise ValueError("no_published_version")
        attempt = (
            s.query(MissionAttempt)
            .filter_by(learner_id=learner_id, mission_id=code, level=level, completed=False,
                       h5p_version_id=version.id)
            .order_by(MissionAttempt.attempt_number.desc()).first()
        )
        if not attempt:
            latest = (
                s.query(MissionAttempt).filter_by(learner_id=learner_id, mission_id=code, level=level)
                .order_by(MissionAttempt.attempt_number.desc()).first()
            )
            attempt = MissionAttempt(
                learner_id=learner_id, mission_id=code, level=level,
                attempt_number=(latest.attempt_number if latest else 0) + 1,
                max_score=0, status="IN_PROGRESS", h5p_version_id=version.id,
            )
            s.add(attempt)
            s.flush()
        return {"attempt_id": attempt.id, "version_id": version.id}


def h5p_event(learner_id, attempt_id, mission_id, level, normalized):
    with session_scope() as s:
        attempt = s.query(MissionAttempt).filter_by(id=attempt_id).one_or_none()
        if not attempt or attempt.learner_id != learner_id:
            raise PermissionError("attempt_not_found")
        n = normalized
        if n["kind"] == "answered":
            s.add(DecisionEvent(
                learner_id=learner_id, attempt_id=attempt.id, mission_id=mission_id, level=level,
                step="h5p", selected_option=(n.get("response") or "answered")[:80],
                score_change=n.get("raw") or 0, is_correct=n.get("correct"),
            ))
        if n.get("raw") is not None and n.get("max") is not None:
            attempt.score = int(n["raw"])
            attempt.max_score = int(n["max"])
            attempt.percentage = (round(n["raw"] / n["max"] * 100) if n["max"]
                                  else (round(n["scaled"] * 100) if n.get("scaled") is not None else None))
        elif n.get("scaled") is not None:
            attempt.percentage = round(n["scaled"] * 100)
        completed = False
        if n["kind"] == "completed":
            attempt.completed = True
            attempt.status = "COMPLETED"
            attempt.completed_at = attempt.completed_at or datetime.utcnow()
            completed = True
        attempt.last_accessed_at = datetime.utcnow()
        attempt.resume_state = {"last_verb": n.get("verb"), "percentage": attempt.percentage}
    if completed:
        recompute_progress(learner_id)
    return {"completed": completed, "percentage": normalized.get("scaled")}
