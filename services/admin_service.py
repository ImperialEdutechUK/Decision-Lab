"""Admin operations: authentication, learner reports, activities, and the H5P pipeline.
Port of the Node admin + h5pAdmin routes. All functions return plain dicts."""
import csv
import io
from datetime import datetime

from sqlalchemy import func, or_

from database.connection import session_scope
from database.models import (
    AdminUser, Learner, LearnerProgress, MissionAttempt, Activity, H5PVersion,
    ActivityEvent, ActivityProgress, ACTIVITY_TYPES, ACTIVITY_STATUSES, OPEN_MODES,
)
from auth.passwords import hash_password, verify_password
from content.registry import TRACK_CODES
from services.h5p_service import validate_package
from services import url_safety
from services.files import sanitize_filename, validate_upload
from config import config


# ── auth ──────────────────────────────────────────────────────────────────────
def create_or_update_admin(email, password, display_name="Administrator"):
    email = email.strip().lower()
    if len(password) < 8:
        raise ValueError("Admin password must be at least 8 characters.")
    with session_scope() as s:
        admin = s.query(AdminUser).filter_by(email=email).one_or_none()
        if admin is None:
            admin = AdminUser(email=email, password_hash=hash_password(password), display_name=display_name)
            s.add(admin)
        else:
            admin.password_hash = hash_password(password)
            admin.display_name = display_name
        s.flush()
        return {"id": admin.id, "email": admin.email, "display_name": admin.display_name}


def authenticate_admin(email, password):
    email = (email or "").strip().lower()
    with session_scope() as s:
        admin = s.query(AdminUser).filter_by(email=email).one_or_none()
        if not admin or not verify_password(password, admin.password_hash):
            return None
        admin.last_login_at = datetime.utcnow()
        return {"id": admin.id, "email": admin.email, "display_name": admin.display_name}


def get_admin(admin_id):
    with session_scope() as s:
        a = s.query(AdminUser).filter_by(id=admin_id).one_or_none()
        return {"id": a.id, "email": a.email, "display_name": a.display_name} if a else None


def admin_count():
    with session_scope() as s:
        return s.query(AdminUser).count()


# ── reports ─────────────────────────────────────────────────────────────────
def overview():
    with session_scope() as s:
        learners = s.query(Learner).count()
        activities = s.query(Activity).count()
        completions = s.query(MissionAttempt).filter_by(completed=True).count()
        avg = s.query(func.avg(MissionAttempt.score)).filter_by(completed=True).scalar()
        recent = (
            s.query(MissionAttempt).order_by(MissionAttempt.last_accessed_at.desc()).limit(15).all()
        )
        rec = []
        for a in recent:
            rec.append({
                "learner": a.learner.display_name or a.learner.email or "-",
                "track": a.level, "activity": a.mission_id,
                "score": f"{a.score}/{a.max_score}", "status": a.status,
                "last_accessed_at": a.last_accessed_at,
            })
        return {
            "learners": learners, "activities": activities, "completions": completions,
            "average_practice_score": round(avg, 2) if avg is not None else None,
            "recent": rec,
        }


def list_learners():
    with session_scope() as s:
        rows = s.query(Learner).order_by(Learner.last_accessed_at.desc()).limit(500).all()
        out = []
        for l in rows:
            p = l.progress
            out.append({
                "id": l.id, "display_name": l.display_name, "email": l.email,
                "external_learner_id": l.external_learner_id,
                "attempts": len(l.attempts),
                "total_points": p.total_points if p else 0,
                "completed_missions": p.completed_missions if p else 0,
                "last_accessed_at": l.last_accessed_at,
            })
        return out


def learner_detail(learner_id):
    with session_scope() as s:
        l = s.query(Learner).filter_by(id=learner_id).one_or_none()
        if not l:
            return None
        attempts = sorted(l.attempts, key=lambda a: (a.mission_id, a.level, a.attempt_number))
        by_track = {}
        for code in TRACK_CODES:
            rows = [a for a in attempts if a.level == code]
            by_track[code] = {
                "attempted": len(set(a.mission_id for a in rows)),
                "completed": len(set(a.mission_id for a in rows if a.completed)),
                "points": sum(a.score for a in rows if a.completed),
            }
        return {
            "learner": {"id": l.id, "display_name": l.display_name, "email": l.email,
                        "external_learner_id": l.external_learner_id, "issuer": l.issuer,
                        "created_at": l.created_at, "last_accessed_at": l.last_accessed_at},
            "by_track": by_track,
            "attempts": [{
                "mission_id": a.mission_id, "track": a.level, "attempt_number": a.attempt_number,
                "score": a.score, "max_score": a.max_score, "status": a.status,
                "feedback_tags": a.feedback_tags or [], "completed_at": a.completed_at,
            } for a in attempts],
        }


def list_activities_admin():
    with session_scope() as s:
        acts = s.query(Activity).order_by(Activity.order_index, Activity.track).all()
        out = []
        for a in acts:
            vs = sorted(a.versions, key=lambda v: v.version, reverse=True)
            out.append({
                "id": a.id, "code": a.code, "track": a.track, "title": a.title,
                "kind": a.kind, "available": a.available,
                "activity_type": a.activity_type, "status": a.status, "url": a.url,
                "embed_url": a.embed_url, "open_mode": a.open_mode, "provider": a.provider,
                "category": a.category, "instructions": a.instructions,
                "description": a.description, "due_date": a.due_date,
                "pass_mark": a.pass_mark, "max_points": a.max_points, "managed": a.managed,
                "versions": [{
                    "id": v.id, "version": v.version, "status": v.status, "title": v.title,
                    "main_library": v.main_library, "file_name": v.file_name, "file_size": v.file_size,
                    "created_at": v.created_at, "published_at": v.published_at,
                } for v in vs],
            })
        return out


def recent_attempts(limit=200):
    with session_scope() as s:
        rows = s.query(MissionAttempt).order_by(MissionAttempt.last_accessed_at.desc()).limit(limit).all()
        return [{
            "learner": a.learner.display_name or a.learner.email or "-",
            "track": a.level, "activity": a.mission_id, "score": a.score, "max_score": a.max_score,
            "status": a.status, "attempt_number": a.attempt_number, "last_accessed_at": a.last_accessed_at,
        } for a in rows]


# ── H5P pipeline ──────────────────────────────────────────────────────────────
def h5p_upload(admin_id, code, track, file_name, data: bytes, title=None):
    if not data:
        raise ValueError("The uploaded file is empty.")
    if len(data) > config.H5P_MAX_UPLOAD_BYTES:
        raise ValueError(f"The package is too large (limit {config.H5P_MAX_UPLOAD_BYTES // (1024 * 1024)} MB).")
    result = validate_package(data)
    with session_scope() as s:
        act = s.query(Activity).filter_by(code=code, track=track).one_or_none()
        if not act:
            raise ValueError(f"No activity {code} in {track}.")
        latest = s.query(H5PVersion).filter_by(activity_id=act.id).order_by(H5PVersion.version.desc()).first()
        v = H5PVersion(
            activity_id=act.id, version=(latest.version if latest else 0) + 1, status="UPLOADED",
            file_name=file_name, file_size=len(data), file_bytes=data,
            title=title or result.get("title") or act.title, main_library=result.get("main_library"),
            h5p_json=result.get("h5p_json"), validation=result.get("message"), uploaded_by_id=admin_id,
        )
        s.add(v)
        s.flush()
        return {"id": v.id, "version": v.version, "status": v.status,
                "validated_ok": result["ok"], "validation": result["message"]}


def h5p_validate(version_id):
    with session_scope() as s:
        v = s.query(H5PVersion).filter_by(id=version_id).one_or_none()
        if not v:
            raise ValueError("not_found")
        if v.status == "PUBLISHED":
            raise ValueError("Published versions cannot be re-validated.")
        result = validate_package(bytes(v.file_bytes))
        v.status = "VALIDATED" if result["ok"] else "UPLOADED"
        v.validation = result["message"]
        if result["ok"]:
            v.title = result.get("title") or v.title
            v.main_library = result.get("main_library") or v.main_library
            v.h5p_json = result.get("h5p_json")
        return {"id": v.id, "status": v.status, "ok": result["ok"], "validation": result["message"]}


def h5p_publish(version_id):
    with session_scope() as s:
        v = s.query(H5PVersion).filter_by(id=version_id).one_or_none()
        if not v:
            raise ValueError("not_found")
        if v.status == "PUBLISHED":
            return {"id": v.id, "status": "PUBLISHED", "already": True}
        result = validate_package(bytes(v.file_bytes))
        if not result["ok"]:
            raise ValueError(result["message"])
        # supersede any currently published version (never overwrite)
        for other in s.query(H5PVersion).filter_by(activity_id=v.activity_id, status="PUBLISHED").all():
            other.status = "UNPUBLISHED"
        v.status = "PUBLISHED"
        v.published_at = datetime.utcnow()
        act = s.query(Activity).filter_by(id=v.activity_id).one()
        act.kind = "H5P"
        act.activity_type = "H5P"
        act.available = True
        act.status = "PUBLISHED"
        return {"id": v.id, "status": "PUBLISHED"}


def h5p_unpublish(version_id):
    with session_scope() as s:
        v = s.query(H5PVersion).filter_by(id=version_id).one_or_none()
        if not v:
            raise ValueError("not_found")
        v.status = "UNPUBLISHED"
        still = s.query(H5PVersion).filter_by(activity_id=v.activity_id, status="PUBLISHED").count()
        if still == 0:
            act = s.query(Activity).filter_by(id=v.activity_id).one()
            act.available = False
            act.status = "UNPUBLISHED"
        return {"id": v.id, "status": "UNPUBLISHED"}


def h5p_version_attempts(version_id):
    with session_scope() as s:
        rows = s.query(MissionAttempt).filter_by(h5p_version_id=version_id).order_by(MissionAttempt.last_accessed_at.desc()).all()
        return [{
            "learner": a.learner.display_name or a.learner.email or "-",
            "score": a.score, "max_score": a.max_score, "percentage": a.percentage, "status": a.status,
        } for a in rows]


# ── Activity management (create / edit / publish) ─────────────────────────────
NATIVE_KINDS = {"NATIVE", "H5P"}


def _kind_for_type(activity_type: str) -> str:
    """Keep the legacy `kind` column coherent so old code paths still branch correctly."""
    t = (activity_type or "NATIVE").upper()
    if t == "NATIVE":
        return "NATIVE"
    if t == "H5P":
        return "H5P"
    return "EXTERNAL"


def _slugify_code(title: str) -> str:
    base = "".join(ch for ch in (title or "").upper() if ch.isalnum() or ch == " ").strip()
    base = "-".join(base.split())[:24] or "ACTIVITY"
    return base


def _unique_code(s, track: str, desired: str) -> str:
    desired = (desired or "").strip().upper()
    if not desired:
        desired = _slugify_code("ACT")
    code = desired
    i = 2
    while s.query(Activity).filter_by(code=code, track=track).one_or_none() is not None:
        code = f"{desired}-{i}"
        i += 1
    return code


def _parse_due(due):
    if not due:
        return None
    if isinstance(due, datetime):
        return due
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(due), fmt)
        except ValueError:
            continue
    return None


def _apply_activity_fields(a: Activity, data: dict):
    a.title = (data.get("title") or a.title or "").strip()
    a.description = data.get("description", a.description)
    a.instructions = data.get("instructions", a.instructions)
    a.category = (data.get("category") or a.category or None)
    a.provider = (data.get("provider") or a.provider or None)
    a.url = (data.get("url") or None)
    a.embed_url = (data.get("embed_url") or None)
    a.open_mode = (data.get("open_mode") or a.open_mode or "NEW_TAB").upper()
    a.est_minutes = data.get("est_minutes", a.est_minutes)
    a.pass_mark = data.get("pass_mark", a.pass_mark)
    a.max_points = data.get("max_points", a.max_points)
    if "due_date" in data:
        a.due_date = _parse_due(data.get("due_date"))


def create_activity(admin_id, data: dict) -> dict:
    """Create an admin-managed activity (external link, embed, video, document, H5P link, ...).
    Validates type, track and (for external types) the URL/allowlist. Returns the new activity id."""
    activity_type = (data.get("activity_type") or "LINK").upper()
    if activity_type not in ACTIVITY_TYPES:
        raise ValueError(f"Unknown activity type: {activity_type}")
    track = (data.get("track") or "").upper()
    if track not in TRACK_CODES:
        raise ValueError(f"Track must be one of {', '.join(TRACK_CODES)}.")
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("A title is required.")
    open_mode = (data.get("open_mode") or "NEW_TAB").upper()
    if open_mode not in OPEN_MODES:
        raise ValueError("open_mode must be NEW_TAB or EMBED.")

    ok, msg = url_safety.validate_activity_urls(activity_type, data.get("url"), data.get("embed_url"), open_mode)
    if not ok:
        raise ValueError(msg)

    status = (data.get("status") or "DRAFT").upper()
    if status not in ACTIVITY_STATUSES:
        raise ValueError("Invalid status.")

    with session_scope() as s:
        code = _unique_code(s, track, data.get("code") or _slugify_code(title))
        max_order = s.query(func.max(Activity.order_index)).scalar() or 0
        a = Activity(
            code=code, track=track, kind=_kind_for_type(activity_type),
            activity_type=activity_type, title=title, order_index=max_order + 1,
            managed=True, status=status, available=(status == "PUBLISHED"),
        )
        _apply_activity_fields(a, data)
        s.add(a)
        s.flush()
        return {"id": a.id, "code": a.code, "track": a.track, "status": a.status}


def update_activity(activity_id, data: dict) -> dict:
    with session_scope() as s:
        a = s.query(Activity).filter_by(id=activity_id).one_or_none()
        if not a:
            raise ValueError("Activity not found.")
        activity_type = (data.get("activity_type") or a.activity_type or "LINK").upper()
        if activity_type not in ACTIVITY_TYPES:
            raise ValueError(f"Unknown activity type: {activity_type}")
        open_mode = (data.get("open_mode") or a.open_mode or "NEW_TAB").upper()
        ok, msg = url_safety.validate_activity_urls(
            activity_type,
            data.get("url", a.url), data.get("embed_url", a.embed_url), open_mode,
        )
        if not ok:
            raise ValueError(msg)
        a.activity_type = activity_type
        a.kind = _kind_for_type(activity_type)
        _apply_activity_fields(a, data)
        if data.get("status"):
            status = data["status"].upper()
            if status not in ACTIVITY_STATUSES:
                raise ValueError("Invalid status.")
            a.status = status
            a.available = (status == "PUBLISHED")
        return {"id": a.id, "code": a.code, "status": a.status}


def move_activity(activity_id, direction: str) -> dict:
    """Reorder within a track by swapping order_index with the adjacent activity."""
    with session_scope() as s:
        a = s.query(Activity).filter_by(id=activity_id).one_or_none()
        if not a:
            raise ValueError("Activity not found.")
        peers = (
            s.query(Activity).filter_by(track=a.track)
            .order_by(Activity.order_index, Activity.created_at).all()
        )
        idx = next((i for i, x in enumerate(peers) if x.id == a.id), None)
        if idx is None:
            return {"id": activity_id, "moved": False}
        swap = idx - 1 if direction == "up" else idx + 1
        if swap < 0 or swap >= len(peers):
            return {"id": activity_id, "moved": False}
        other = peers[swap]
        a.order_index, other.order_index = other.order_index, a.order_index
        return {"id": activity_id, "moved": True}


def set_activity_status(activity_id, status: str) -> dict:
    status = (status or "").upper()
    if status not in ACTIVITY_STATUSES:
        raise ValueError("Invalid status.")
    with session_scope() as s:
        a = s.query(Activity).filter_by(id=activity_id).one_or_none()
        if not a:
            raise ValueError("Activity not found.")
        a.status = status
        a.available = (status == "PUBLISHED")
        return {"id": a.id, "status": a.status, "available": a.available}


def delete_activity(activity_id) -> dict:
    """Delete a managed activity ONLY when it is safe - i.e. no learner records reference it.
    If any attempts/progress/events exist, we refuse and keep the data (archive instead)."""
    with session_scope() as s:
        a = s.query(Activity).filter_by(id=activity_id).one_or_none()
        if not a:
            raise ValueError("Activity not found.")
        if not a.managed:
            raise ValueError("Built-in catalogue activities cannot be deleted; unpublish them instead.")
        refs = (
            s.query(ActivityProgress).filter_by(activity_id=a.id).count()
            + s.query(ActivityEvent).filter_by(activity_id=a.id).count()
            + s.query(MissionAttempt).filter_by(mission_id=a.code, level=a.track).count()
        )
        if refs:
            a.status = "ARCHIVED"
            a.available = False
            return {"id": a.id, "deleted": False, "archived": True,
                    "message": "Learner records exist, so the activity was archived (not deleted)."}
        s.delete(a)
        return {"id": activity_id, "deleted": True, "archived": False}


def get_activity_admin(activity_id) -> dict | None:
    with session_scope() as s:
        a = s.query(Activity).filter_by(id=activity_id).one_or_none()
        if not a:
            return None
        return {
            "id": a.id, "code": a.code, "track": a.track, "title": a.title,
            "description": a.description, "instructions": a.instructions, "category": a.category,
            "activity_type": a.activity_type, "kind": a.kind, "status": a.status,
            "available": a.available, "url": a.url, "embed_url": a.embed_url,
            "open_mode": a.open_mode, "provider": a.provider, "due_date": a.due_date,
            "pass_mark": a.pass_mark, "max_points": a.max_points, "managed": a.managed,
            "est_minutes": a.est_minutes,
            "file_name": a.file_name, "has_file": bool(a.file_bytes),
            "guideline_file_name": a.guideline_file_name, "has_guideline_file": bool(a.guideline_file_bytes),
        }


# ── Activity file attachments (document + guideline) ──────────────────────────
def save_activity_file(activity_id, file_name, data: bytes, mime: str) -> dict:
    """Store an uploaded DOCUMENT file's bytes on the activity row (validated)."""
    ok, msg = validate_upload(file_name, data)
    if not ok:
        raise ValueError(msg)
    with session_scope() as s:
        a = s.query(Activity).filter_by(id=activity_id).one_or_none()
        if not a:
            raise ValueError("Activity not found.")
        a.file_name = sanitize_filename(file_name)
        a.file_bytes = data
        a.file_mime = mime or "application/octet-stream"
        return {"id": a.id, "file_name": a.file_name}


def clear_activity_file(activity_id) -> dict:
    with session_scope() as s:
        a = s.query(Activity).filter_by(id=activity_id).one_or_none()
        if a:
            a.file_name = a.file_bytes = a.file_mime = None
    return {"id": activity_id, "cleared": True}


def save_guideline_file(activity_id, file_name, data: bytes, mime: str) -> dict:
    """Store an optional supporting file for an activity's learner guidelines (validated)."""
    ok, msg = validate_upload(file_name, data)
    if not ok:
        raise ValueError(msg)
    with session_scope() as s:
        a = s.query(Activity).filter_by(id=activity_id).one_or_none()
        if not a:
            raise ValueError("Activity not found.")
        a.guideline_file_name = sanitize_filename(file_name)
        a.guideline_file_bytes = data
        a.guideline_file_mime = mime or "application/octet-stream"
        return {"id": a.id, "file_name": a.guideline_file_name}


def clear_guideline_file(activity_id) -> dict:
    with session_scope() as s:
        a = s.query(Activity).filter_by(id=activity_id).one_or_none()
        if a:
            a.guideline_file_name = a.guideline_file_bytes = a.guideline_file_mime = None
    return {"id": activity_id, "cleared": True}


def get_activity_file(activity_id) -> tuple[str, bytes, str] | None:
    with session_scope() as s:
        a = s.query(Activity).filter_by(id=activity_id).one_or_none()
        if not a or not a.file_bytes:
            return None
        return a.file_name or "document", bytes(a.file_bytes), a.file_mime or "application/octet-stream"


def get_guideline_file(activity_id) -> tuple[str, bytes, str] | None:
    with session_scope() as s:
        a = s.query(Activity).filter_by(id=activity_id).one_or_none()
        if not a or not a.guideline_file_bytes:
            return None
        return (a.guideline_file_name or "guidelines", bytes(a.guideline_file_bytes),
                a.guideline_file_mime or "application/octet-stream")


# ── Learner search + unified reporting ────────────────────────────────────────
def search_learners(query: str):
    q = (query or "").strip().lower()
    with session_scope() as s:
        qry = s.query(Learner)
        if q:
            like = f"%{q}%"
            qry = qry.filter(or_(
                func.lower(Learner.email).like(like),
                func.lower(Learner.display_name).like(like),
                func.lower(Learner.external_learner_id).like(like),
            ))
        rows = qry.order_by(Learner.last_accessed_at.desc()).limit(500).all()
        out = []
        for l in rows:
            p = l.progress
            out.append({
                "id": l.id, "display_name": l.display_name, "email": l.email,
                "external_learner_id": l.external_learner_id, "issuer": l.issuer,
                "attempts": len(l.attempts),
                "total_points": p.total_points if p else 0,
                "completed_missions": p.completed_missions if p else 0,
                "last_accessed_at": l.last_accessed_at,
            })
        return out


def _activity_lookup(s):
    return {(a.code, a.track): a for a in s.query(Activity).all()}


def report_rows(activity_code=None, track=None, status=None, learner_q=None,
                date_from=None, date_to=None):
    """Unified per-(learner, activity) report across BOTH native/H5P attempts (MissionAttempt) and
    external activities (ActivityProgress). Returns real persisted rows only."""
    df = _parse_due(date_from) if isinstance(date_from, str) else date_from
    dt = _parse_due(date_to) if isinstance(date_to, str) else date_to
    lq = (learner_q or "").strip().lower()

    def _match_common(code, trk, learner):
        if activity_code and code != activity_code:
            return False
        if track and trk != track:
            return False
        if lq:
            hay = f"{learner.email or ''} {learner.display_name or ''} {learner.external_learner_id or ''}".lower()
            if lq not in hay:
                return False
        return True

    rows = []
    with session_scope() as s:
        acts = _activity_lookup(s)
        # native + H5P attempts
        for a in s.query(MissionAttempt).all():
            learner = a.learner
            if not _match_common(a.mission_id, a.level, learner):
                continue
            last = a.last_accessed_at
            if df and last and last < df:
                continue
            if dt and last and last > dt:
                continue
            st = a.status or ("COMPLETED" if a.completed else "IN_PROGRESS")
            if status and st != status:
                continue
            act = acts.get((a.mission_id, a.level))
            atype = (act.activity_type if act else None) or "H5P"
            rows.append({
                "learner": learner.display_name or learner.email or "-",
                "email": learner.email, "learner_id": learner.id,
                "code": a.mission_id, "title": (act.title if act else a.mission_id),
                "type": atype, "track": a.level, "status": st,
                "score": a.score, "max_score": a.max_score, "percentage": a.percentage,
                "score_verified": True if atype == "H5P" else None,
                "attempts": a.attempt_number, "last_accessed_at": last,
                "completed_at": a.completed_at,
            })
        # external activity progress
        for p in s.query(ActivityProgress).all():
            learner = s.query(Learner).filter_by(id=p.learner_id).one_or_none()
            if not learner or not _match_common(p.code, p.track, learner):
                continue
            last = p.last_access_at
            if df and last and last < df:
                continue
            if dt and last and last > dt:
                continue
            st = p.completion_status or "NOT_STARTED"
            if status and st != status:
                continue
            act = acts.get((p.code, p.track))
            rows.append({
                "learner": learner.display_name or learner.email or "-",
                "email": learner.email, "learner_id": learner.id,
                "code": p.code, "title": (act.title if act else p.code),
                "type": (act.activity_type if act else "LINK"), "track": p.track, "status": st,
                "score": p.best_score, "max_score": p.best_max_score, "percentage": p.progress_pct,
                "score_verified": bool(p.score_verified),
                "attempts": p.attempt_count, "last_accessed_at": last,
                "completed_at": p.completed_at,
            })
    rows.sort(key=lambda r: (r["last_accessed_at"] or datetime.min), reverse=True)
    return rows


def incomplete_report(**filters):
    return [r for r in report_rows(**filters) if r["status"] != "COMPLETED"]


def integration_limitations():
    """Activities whose score/completion we cannot verify without a configured integration, plus
    any recent ERROR events. Used to be transparent about what is and isn't tracked."""
    with session_scope() as s:
        acts = s.query(Activity).filter(Activity.managed == True).all()  # noqa: E712
        verified_activity_ids = {
            e.activity_id for e in s.query(ActivityEvent).filter_by(verified=True).all() if e.activity_id
        }
        limited = []
        for a in acts:
            if a.activity_type == "H5P":
                continue
            limited.append({
                "code": a.code, "track": a.track, "title": a.title, "type": a.activity_type,
                "status": a.status, "provider": a.provider,
                "has_verified_scores": a.id in verified_activity_ids,
                "note": ("Launch/access is tracked. Score & completion are NOT received from this "
                         "provider unless a supported integration (e.g. xAPI / LTI-AGS) is configured "
                         "and confirmed."),
            })
        errors = (
            s.query(ActivityEvent).filter_by(event_type="ERROR")
            .order_by(ActivityEvent.created_at.desc()).limit(50).all()
        )
        err_rows = [{
            "code": e.code, "track": e.track, "when": e.created_at,
            "message": (e.detail or {}).get("message") if e.detail else None,
        } for e in errors]
        return {"limited_activities": limited, "errors": err_rows}


def tracking_csv(**filters) -> str:
    rows = report_rows(**filters)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["learner", "email", "learner_id", "activity_code", "title", "type", "track",
                "status", "score", "max_score", "percentage", "score_verified", "attempts",
                "last_accessed_at", "completed_at"])
    for r in rows:
        w.writerow([
            r["learner"], r["email"] or "", r["learner_id"], r["code"], r["title"], r["type"],
            r["track"], r["status"], "" if r["score"] is None else r["score"],
            "" if r["max_score"] is None else r["max_score"],
            "" if r["percentage"] is None else r["percentage"],
            "" if r["score_verified"] is None else ("yes" if r["score_verified"] else "no"),
            r["attempts"],
            r["last_accessed_at"].isoformat() if r["last_accessed_at"] else "",
            r["completed_at"].isoformat() if r["completed_at"] else "",
        ])
    return buf.getvalue()
