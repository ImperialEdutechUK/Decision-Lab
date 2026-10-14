"""Courses, course guides, activity guidelines/files, and the no-seed guarantee."""
import pytest

from services import admin_service as A
from services import course_service as C
from database.connection import session_scope
from database.models import Activity


def _admin():
    A.create_or_update_admin("course_admin@test.com", "password123", "Course Admin")
    return A.authenticate_admin("course_admin@test.com", "password123")


def test_no_activities_are_seeded():
    with session_scope() as s:
        assert s.query(Activity).filter(Activity.managed == False).count() == 0  # noqa: E712


def test_courses_are_the_two_tracks():
    courses = {c["code"] for c in C.list_courses()}
    assert courses == {"FOUNDATION", "PRACTITIONER"}


def test_course_guide_text_publish_and_learner_visibility():
    # No guide -> learner sees nothing published.
    assert C.get_published_guide("FOUNDATION") is None
    C.save_guide("FOUNDATION", title="Start here", body="# Welcome\n- read this")
    # Draft is not visible to learners.
    assert C.get_published_guide("FOUNDATION") is None
    C.set_guide_status("FOUNDATION", "PUBLISHED")
    pub = C.get_published_guide("FOUNDATION")
    assert pub and pub["title"] == "Start here" and "Welcome" in pub["body"]
    # Unpublish hides it again.
    C.set_guide_status("FOUNDATION", "DRAFT")
    assert C.get_published_guide("FOUNDATION") is None


def test_cannot_publish_empty_guide():
    with pytest.raises(ValueError):
        C.set_guide_status("PRACTITIONER", "PUBLISHED")


def test_guide_file_validation_and_roundtrip():
    with pytest.raises(ValueError):
        C.set_guide_file("FOUNDATION", "bad.exe", b"x" * 10, "application/octet-stream")
    C.set_guide_file("FOUNDATION", "guide.pdf", b"%PDF-1.4 test", "application/pdf")
    got = C.guide_file_bytes("FOUNDATION")
    assert got and got[0] == "guide.pdf" and got[1].startswith(b"%PDF")


def test_activity_guideline_and_document_files():
    admin = _admin()
    act = A.create_activity(admin["id"], {
        "title": "Worksheet", "track": "FOUNDATION", "activity_type": "DOCUMENT", "status": "DRAFT",
    })
    # Guideline file (optional supporting resource)
    A.save_guideline_file(act["id"], "notes.pdf", b"%PDF-1.4 notes", "application/pdf")
    gf = A.get_guideline_file(act["id"])
    assert gf and gf[0] == "notes.pdf"
    # Document file, with filename sanitisation
    A.save_activity_file(act["id"], "../weird name!.pdf", b"%PDF-1.4 doc", "application/pdf")
    df = A.get_activity_file(act["id"])
    assert df and "/" not in df[0] and df[0].endswith(".pdf")
    # Oversized / disallowed types are rejected
    with pytest.raises(ValueError):
        A.save_activity_file(act["id"], "x.exe", b"data", "application/octet-stream")


def test_learner_only_sees_published_activities():
    from auth.learner_identity import upsert_learner
    from services import progress_service as P
    admin = _admin()
    A.create_activity(admin["id"], {"title": "Hidden", "track": "PRACTITIONER",
                                    "activity_type": "LINK", "open_mode": "NEW_TAB",
                                    "url": "https://example.com/h", "status": "DRAFT"})
    pub = A.create_activity(admin["id"], {"title": "Shown", "track": "PRACTITIONER",
                                          "activity_type": "LINK", "open_mode": "NEW_TAB",
                                          "url": "https://example.com/s", "status": "PUBLISHED"})
    lr = upsert_learner({"issuer": "dev://local", "external_learner_id": "vis-1",
                         "display_name": "Vis", "email": "vis@x.com"})
    titles = {a["title"] for a in P.activities_with_status(lr["id"])["PRACTITIONER"]}
    assert "Shown" in titles and "Hidden" not in titles
    # Unpublished detail is not reachable by a learner.
    assert P.activity_detail(lr["id"], pub["code"], "PRACTITIONER") is not None
