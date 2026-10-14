"""Activity catalogue queries."""
from database.connection import session_scope
from database.models import Activity, H5PVersion


def list_activities_for_track(track: str):
    with session_scope() as s:
        rows = s.query(Activity).filter(Activity.track == track).order_by(Activity.order_index).all()
        return [_activity_dict(a) for a in rows]


def get_activity(code: str, track: str):
    with session_scope() as s:
        a = s.query(Activity).filter(Activity.code == code, Activity.track == track).one_or_none()
        return _activity_dict(a) if a else None


def published_h5p(activity_id: str):
    with session_scope() as s:
        v = (
            s.query(H5PVersion)
            .filter(H5PVersion.activity_id == activity_id, H5PVersion.status == "PUBLISHED")
            .order_by(H5PVersion.version.desc())
            .first()
        )
        if not v:
            return None
        return {"id": v.id, "version": v.version, "title": v.title, "main_library": v.main_library}


def _activity_dict(a: Activity):
    return {
        "id": a.id, "code": a.code, "track": a.track, "title": a.title,
        "description": a.description, "est_minutes": a.est_minutes,
        "kind": a.kind, "available": a.available, "order_index": a.order_index,
    }
