"""Generic activity tracking: launch/access persistence, no duplicate progress rows, verified-only
scores, and that report rows + CSV reflect persisted data."""
from auth.learner_identity import upsert_learner
from services import admin_service as A
from services import tracking_service as T


def _admin():
    A.create_or_update_admin("trk_admin@test.com", "password123", "Trk")
    return A.authenticate_admin("trk_admin@test.com", "password123")


def _learner(sub):
    return upsert_learner({"issuer": "dev://local", "external_learner_id": sub,
                           "display_name": sub, "email": f"{sub}@x.com"})


def _ext_activity():
    admin = _admin()
    return A.create_activity(admin["id"], {
        "title": "Ext quiz", "track": "FOUNDATION", "activity_type": "EXTERNAL_QUIZ",
        "open_mode": "NEW_TAB", "url": "https://example.com/q", "status": "PUBLISHED",
    })


def test_launch_and_access_persist_without_duplicates():
    act = _ext_activity()
    lr = _learner("T-1")
    T.touch_access(lr["id"], activity_id=act["id"])
    T.record_launch(lr["id"], activity_id=act["id"])
    T.record_launch(lr["id"], activity_id=act["id"])
    p = T.progress_one(lr["id"], act["id"])
    assert p is not None
    assert p["launch_count"] == 2
    assert p["view_count"] >= 1
    assert p["completion_status"] == "IN_PROGRESS"
    # one durable progress row only
    allp = T.progress_for_learner(lr["id"])
    assert len(allp) == 1
    # a plain launch is NOT a verified score
    assert p["score_verified"] is False and p["best_score"] is None


def test_verified_result_marks_score_and_completion():
    act = _ext_activity()
    lr = _learner("T-2")
    T.record_launch(lr["id"], activity_id=act["id"])
    T.record_verified_result(lr["id"], activity_id=act["id"], score=8, max_score=10,
                             success=True, completed=True, source="XAPI")
    p = T.progress_one(lr["id"], act["id"])
    assert p["score_verified"] is True
    assert p["best_score"] == 8 and p["best_max_score"] == 10
    assert p["completion_status"] == "COMPLETED" and p["passed"] is True


def test_report_rows_and_csv_include_external():
    act = _ext_activity()
    lr = _learner("T-3")
    T.record_launch(lr["id"], activity_id=act["id"])
    rows = A.report_rows(activity_code=act["code"])
    mine = [r for r in rows if r["learner_id"] == lr["id"]]
    assert mine and mine[0]["status"] in ("IN_PROGRESS", "ACCESSED")
    assert mine[0]["score_verified"] is False
    csv_text = A.tracking_csv(activity_code=act["code"])
    assert "activity_code" in csv_text and act["code"] in csv_text


def test_incomplete_report_excludes_completed():
    act = _ext_activity()
    lr = _learner("T-4")
    T.record_verified_result(lr["id"], activity_id=act["id"], score=10, max_score=10, completed=True)
    inc = A.incomplete_report(activity_code=act["code"])
    assert all(r["learner_id"] != lr["id"] for r in inc)
