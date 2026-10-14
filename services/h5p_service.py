"""H5P package handling with the stdlib (zipfile/json) - validate, read entries, normalize xAPI.
Port of the Node services/h5p.js. No third-party dependency needed.
"""
import io
import json
import zipfile

_MIME = {
    ".json": "application/json", ".js": "text/javascript", ".css": "text/css",
    ".html": "text/html", ".htm": "text/html", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp",
    ".ico": "image/x-icon", ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf",
    ".otf": "font/otf", ".eot": "application/vnd.ms-fontobject", ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4", ".wav": "audio/wav", ".ogg": "audio/ogg", ".mp4": "video/mp4",
    ".webm": "video/webm", ".txt": "text/plain", ".xml": "application/xml", ".vtt": "text/vtt",
}


def mime_for(path: str) -> str:
    i = path.rfind(".")
    return _MIME.get(path[i:].lower() if i >= 0 else "", "application/octet-stream")


def validate_package(data: bytes) -> dict:
    """Return {ok, title, main_library, h5p_json, message}."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return {"ok": False, "message": "Not a readable zip/.h5p archive."}
    names = set(n.lstrip("/") for n in zf.namelist())
    if "h5p.json" not in names:
        return {"ok": False, "message": "Missing h5p.json at the package root."}
    if "content/content.json" not in names:
        return {"ok": False, "message": "Missing content/content.json."}
    try:
        h5p_json = json.loads(zf.read("h5p.json").decode("utf-8"))
    except Exception:
        return {"ok": False, "message": "h5p.json is not valid JSON."}
    if not h5p_json.get("mainLibrary"):
        return {"ok": False, "message": "h5p.json has no mainLibrary."}
    has_libs = any(n.count("/") == 1 and n.endswith("/library.json") for n in names)
    if not has_libs:
        return {"ok": False, "message": "No H5P library folders found in the package."}
    return {
        "ok": True,
        "title": str(h5p_json.get("title")) if h5p_json.get("title") else None,
        "main_library": h5p_json.get("mainLibrary"),
        "h5p_json": h5p_json,
        "message": "Valid H5P package.",
    }


def read_entry(data: bytes, rel_path: str):
    """Return (bytes, content_type) for an entry, or None. Blocks path traversal."""
    clean = str(rel_path).lstrip("/").replace("../", "").replace("..\\", "")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return None
    try:
        payload = zf.read(clean)
    except KeyError:
        return None
    return payload, mime_for(clean)


def normalize_xapi(statement: dict) -> dict:
    verb_id = (statement or {}).get("verb", {}).get("id", "")
    verb = verb_id.split("/")[-1] if verb_id else ""
    result = (statement or {}).get("result", {}) or {}
    score = result.get("score", {}) or {}

    def num(v):
        return v if isinstance(v, (int, float)) else None

    out = {
        "verb": verb,
        "kind": "other",
        "correct": result.get("success") if isinstance(result.get("success"), bool) else None,
        "raw": num(score.get("raw")),
        "max": num(score.get("max")),
        "scaled": num(score.get("scaled")),
        "completion": result.get("completion") if isinstance(result.get("completion"), bool) else None,
        "response": (str(result.get("response"))[:500] if isinstance(result.get("response"), str) else None),
    }
    if verb in ("completed", "passed", "failed") or out["completion"] is True:
        out["kind"] = "completed"
    elif verb == "answered":
        out["kind"] = "answered"
    return out
