"""Production companion service (FastAPI) for the two things Streamlit cannot do itself:

  1. LTI 1.3 launch  - receive the OIDC login + id_token form_post, validate it, and hand the
     learner to the Streamlit app with a signed, single-use launch token (?launch=...).
  2. H5P serving + xAPI - stream package files from the database and receive xAPI statements,
     normalizing them into the same progress tables.

Run alongside Streamlit:
    uvicorn companion.lti_app:app --host 0.0.0.0 --port 8000

This is the documented "closest functional alternative" to in-process handling, because a
Streamlit script cannot accept a cross-site POST or host an xAPI endpoint.
"""
import secrets
import time
from datetime import datetime, timedelta

import jwt
from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from config import config
from database.init_db import init_db
from database.connection import session_scope
from database.models import LaunchNonce, H5PVersion
from auth.tokens import mint_launch_token, verify_session
from auth.learner_identity import get_learner
from services.h5p_service import read_entry, normalize_xapi
from services import progress_service as P

CLAIM_MESSAGE = "https://purl.imsglobal.org/spec/lti/claim/message_type"
CLAIM_DEPLOY = "https://purl.imsglobal.org/spec/lti/claim/deployment_id"
CLAIM_TARGET = "https://purl.imsglobal.org/spec/lti/claim/target_link_uri"

app = FastAPI(title=f"{config.APP_NAME} companion")
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.STREAMLIT_URL] if config.STREAMLIT_URL else ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

_jwks_client = None


def jwks():
    global _jwks_client
    if _jwks_client is None and config.LTI_JWKS_URL:
        _jwks_client = jwt.PyJWKClient(config.LTI_JWKS_URL)
    return _jwks_client


def _store_state(state, nonce, issuer):
    with session_scope() as s:
        s.add(LaunchNonce(nonce=f"state:{state}:{nonce}", issuer=issuer, expires_at=datetime.utcnow() + timedelta(minutes=10)))


def _consume_state(state, nonce, issuer):
    key = f"state:{state}:{nonce}"
    with session_scope() as s:
        row = s.query(LaunchNonce).filter_by(nonce=key).one_or_none()
        if not row or row.used_at or row.expires_at < datetime.utcnow():
            return False
        row.used_at = datetime.utcnow()
        return True


@app.get("/health")
def health():
    return {"status": "ok", "lti": bool(config.LTI_ISSUER), "time": datetime.utcnow().isoformat()}


# ── LTI 1.3 ──────────────────────────────────────────────────────────────────
@app.api_route("/lti/login", methods=["GET", "POST"])
async def lti_login(request: Request):
    params = dict(request.query_params)
    if request.method == "POST":
        params.update(dict(await request.form()))
    iss = params.get("iss")
    login_hint = params.get("login_hint")
    if iss != config.LTI_ISSUER:
        return Response("Unrecognised LTI issuer.", status_code=400)
    if not login_hint:
        return Response("Missing login_hint.", status_code=400)
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    _store_state(state, nonce, iss)
    auth = (
        f"{config.LTI_AUTH_LOGIN_URL}?response_type=id_token&response_mode=form_post&scope=openid"
        f"&prompt=none&client_id={config.LTI_CLIENT_ID}"
        f"&redirect_uri={config.COMPANION_PUBLIC_URL}/lti/launch"
        f"&login_hint={login_hint}&state={state}&nonce={nonce}"
    )
    if params.get("lti_message_hint"):
        auth += f"&lti_message_hint={params['lti_message_hint']}"
    return RedirectResponse(auth, status_code=302)


@app.post("/lti/launch")
async def lti_launch(request: Request):
    form = dict(await request.form())
    id_token = form.get("id_token")
    state = form.get("state")
    if not id_token or not state:
        return Response("Missing id_token/state.", status_code=400)
    try:
        signing_key = jwks().get_signing_key_from_jwt(id_token).key
        payload = jwt.decode(id_token, signing_key, algorithms=["RS256"], audience=config.LTI_CLIENT_ID, issuer=config.LTI_ISSUER)
    except Exception:
        return Response("Could not validate the LMS launch token.", status_code=401)
    nonce = payload.get("nonce")
    if not nonce or not _consume_state(state, nonce, config.LTI_ISSUER):
        return Response("State/nonce validation failed.", status_code=401)
    if payload.get(CLAIM_MESSAGE) != "LtiResourceLinkRequest":
        return Response("Unsupported LTI message type.", status_code=400)
    if payload.get(CLAIM_DEPLOY) != config.LTI_DEPLOYMENT_ID:
        return Response("Unknown LTI deployment.", status_code=400)

    mission = None
    tlu = payload.get(CLAIM_TARGET)
    if tlu and "mission=" in tlu:
        mission = tlu.split("mission=")[-1].split("&")[0]

    token = mint_launch_token(
        sub=payload["sub"], email=payload.get("email"), name=payload.get("name"),
        given_name=payload.get("given_name"), family_name=payload.get("family_name"), mission=mission,
    )
    return RedirectResponse(f"{config.STREAMLIT_URL}/?launch={token}", status_code=302)


# ── H5P serving + xAPI ───────────────────────────────────────────────────────
@app.get("/h5p/play/{version_id}/{path:path}")
def h5p_file(version_id: str, path: str):
    with session_scope() as s:
        v = s.query(H5PVersion).filter_by(id=version_id).one_or_none()
        if not v or v.status != "PUBLISHED":
            return Response("Not found", status_code=404)
        data = bytes(v.file_bytes)
    entry = read_entry(data, path or "h5p.json")
    if not entry:
        return Response("Not found in package", status_code=404)
    body, ctype = entry
    return Response(content=body, media_type=ctype, headers={"Cache-Control": "private, max-age=300"})


@app.post("/h5p/event")
async def h5p_event(request: Request):
    body = await request.json()
    lid = verify_session(body.get("token", ""))
    if not lid or not get_learner(lid):
        return JSONResponse({"error": "not_authenticated"}, status_code=401)
    normalized = normalize_xapi(body.get("statement") or {})
    try:
        r = P.h5p_event(lid, body.get("attemptId"), body.get("code"), body.get("level"), normalized)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse(r)


@app.get("/", response_class=HTMLResponse)
def root():
    return f"<p>{config.APP_NAME} companion is running. Launch the app from your LMS.</p>"
