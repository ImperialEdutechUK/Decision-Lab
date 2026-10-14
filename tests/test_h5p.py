import io
import json
import zipfile

from services.h5p_service import validate_package, read_entry, normalize_xapi
from services import admin_service as A


def _pkg():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("h5p.json", json.dumps({"title": "Demo", "mainLibrary": "H5P.MultiChoice"}))
        z.writestr("content/content.json", json.dumps({"question": "?"}))
        z.writestr("H5P.MultiChoice-1.16/library.json", json.dumps({"machineName": "H5P.MultiChoice"}))
    return buf.getvalue()


def test_validate_good():
    r = validate_package(_pkg())
    assert r["ok"] and r["main_library"] == "H5P.MultiChoice"


def test_validate_missing_content():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("h5p.json", json.dumps({"mainLibrary": "X"}))
    assert validate_package(buf.getvalue())["ok"] is False


def test_validate_not_zip():
    assert validate_package(b"nope")["ok"] is False


def test_read_entry_and_traversal():
    data = _pkg()
    body, ctype = read_entry(data, "h5p.json")
    assert b"mainLibrary" in body and "json" in ctype
    assert read_entry(data, "../../etc/passwd") is None


def test_normalize_xapi():
    completed = normalize_xapi({"verb": {"id": "http://adlnet.gov/expapi/verbs/completed"},
                                "result": {"completion": True, "score": {"raw": 8, "max": 10, "scaled": 0.8}}})
    assert completed["kind"] == "completed" and completed["raw"] == 8 and completed["max"] == 10


def test_admin_and_h5p_publish_flow():
    A.create_or_update_admin("admin@test.com", "password123", "Root")
    admin = A.authenticate_admin("admin@test.com", "password123")
    assert admin and A.authenticate_admin("admin@test.com", "bad") is None
    # Admin creates an H5P activity, then uploads + publishes a package to it.
    act = A.create_activity(admin["id"], {
        "title": "H5P quiz", "track": "FOUNDATION", "activity_type": "H5P", "status": "DRAFT",
    })
    up = A.h5p_upload(admin["id"], act["code"], act["track"], "demo.h5p", _pkg(), "Demo")
    assert up["validated_ok"]
    A.h5p_validate(up["id"])
    pub = A.h5p_publish(up["id"])
    assert pub["status"] == "PUBLISHED"
    acts = {a["id"]: a for a in A.list_activities_admin()}
    assert acts[act["id"]]["kind"] == "H5P" and acts[act["id"]]["available"]
