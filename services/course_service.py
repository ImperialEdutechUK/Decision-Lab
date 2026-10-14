"""Courses and course guides - all admin-managed, stored persistently in the database.

A course is a track (PRINCE2 Foundation / PRINCE2 Practitioner). Each course has optional editable
information and one course guide. A guide can carry rich text, an uploaded file, or both, and is
shown to learners only once PUBLISHED.
"""
from datetime import datetime

from database.connection import session_scope
from database.models import Course, CourseGuide, GUIDE_STATUSES
from content.registry import TRACK_CODES, TRACKS
from services.files import sanitize_filename, validate_upload


# ── courses ─────────────────────────────────────────────────────────────────────
def ensure_courses():
    """Create the two course rows on demand (names only, no sample content)."""
    with session_scope() as s:
        for code in TRACK_CODES:
            if s.query(Course).filter_by(code=code).one_or_none() is None:
                s.add(Course(code=code, name=TRACKS[code]["name"]))


def get_course(code: str) -> dict | None:
    with session_scope() as s:
        c = s.query(Course).filter_by(code=code).one_or_none()
        name = TRACKS.get(code, {}).get("name", code)
        if not c:
            return {"code": code, "name": name, "info": None}
        return {"code": c.code, "name": c.name or name, "info": c.info}


def list_courses() -> list[dict]:
    ensure_courses()
    return [get_course(code) for code in TRACK_CODES]


def update_course_info(code: str, info: str) -> dict:
    if code not in TRACK_CODES:
        raise ValueError("Unknown course.")
    with session_scope() as s:
        c = s.query(Course).filter_by(code=code).one_or_none()
        if c is None:
            c = Course(code=code, name=TRACKS[code]["name"])
            s.add(c)
        c.info = (info or "").strip() or None
        return {"code": code, "info": c.info}


# ── course guides ─────────────────────────────────────────────────────────────
def _guide_dict(g: CourseGuide, with_file=False) -> dict:
    d = {
        "id": g.id, "course_code": g.course_code, "title": g.title, "body": g.body,
        "status": g.status, "has_file": bool(g.file_bytes), "file_name": g.file_name,
        "file_mime": g.file_mime, "updated_at": g.updated_at, "published_at": g.published_at,
    }
    if with_file and g.file_bytes:
        d["file_bytes"] = bytes(g.file_bytes)
    return d


def get_guide(course_code: str, with_file=False) -> dict | None:
    with session_scope() as s:
        g = s.query(CourseGuide).filter_by(course_code=course_code).one_or_none()
        return _guide_dict(g, with_file=with_file) if g else None


def get_published_guide(course_code: str, with_file=False) -> dict | None:
    """The guide a learner should see, or None when there is no published guide."""
    g = get_guide(course_code, with_file=with_file)
    if g and g["status"] == "PUBLISHED" and (g["body"] or g["has_file"]):
        return g
    return None


def _get_or_create(s, course_code):
    if course_code not in TRACK_CODES:
        raise ValueError("Unknown course.")
    g = s.query(CourseGuide).filter_by(course_code=course_code).one_or_none()
    if g is None:
        g = CourseGuide(course_code=course_code, status="DRAFT")
        s.add(g)
        s.flush()
    return g


def save_guide(course_code: str, *, title=None, body=None) -> dict:
    """Create or update the text of a course's guide. Does not change the file or status."""
    with session_scope() as s:
        g = _get_or_create(s, course_code)
        g.title = (title or "").strip() or None
        g.body = (body or "").strip() or None
        g.updated_at = datetime.utcnow()
        return _guide_dict(g)


def set_guide_file(course_code: str, file_name: str, data: bytes, mime: str) -> dict:
    """Attach (or replace) the guide's uploaded file after validating it."""
    ok, msg = validate_upload(file_name, data)
    if not ok:
        raise ValueError(msg)
    with session_scope() as s:
        g = _get_or_create(s, course_code)
        g.file_name = sanitize_filename(file_name)
        g.file_bytes = data
        g.file_mime = mime or "application/octet-stream"
        g.updated_at = datetime.utcnow()
        return _guide_dict(g)


def remove_guide_file(course_code: str) -> dict:
    with session_scope() as s:
        g = _get_or_create(s, course_code)
        g.file_name = g.file_bytes = g.file_mime = None
        g.updated_at = datetime.utcnow()
        return _guide_dict(g)


def set_guide_status(course_code: str, status: str) -> dict:
    status = (status or "").upper()
    if status not in GUIDE_STATUSES:
        raise ValueError("Status must be DRAFT or PUBLISHED.")
    with session_scope() as s:
        g = _get_or_create(s, course_code)
        if status == "PUBLISHED" and not (g.body or g.file_bytes):
            raise ValueError("Add guide text or a file before publishing.")
        g.status = status
        g.published_at = datetime.utcnow() if status == "PUBLISHED" else None
        g.updated_at = datetime.utcnow()
        return _guide_dict(g)


def delete_guide(course_code: str) -> dict:
    with session_scope() as s:
        g = s.query(CourseGuide).filter_by(course_code=course_code).one_or_none()
        if g:
            s.delete(g)
    return {"course_code": course_code, "deleted": True}


def guide_file_bytes(course_code: str) -> tuple[str, bytes, str] | None:
    with session_scope() as s:
        g = s.query(CourseGuide).filter_by(course_code=course_code).one_or_none()
        if not g or not g.file_bytes:
            return None
        return g.file_name or "guide", bytes(g.file_bytes), g.file_mime or "application/octet-stream"
