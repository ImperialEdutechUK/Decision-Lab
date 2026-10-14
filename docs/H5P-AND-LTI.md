# H5P playback and LTI 1.3 - the companion service

## Why a companion is needed

Streamlit runs a Python script top to bottom on each interaction. It does not expose raw HTTP
request handling, so it cannot:

1. receive an LTI 1.3 OIDC `form_post` (the LMS POSTs a signed `id_token` to a redirect URI), or
2. host an xAPI endpoint that an embedded H5P iframe can POST results to.

Those two run in a small FastAPI companion (`companion/lti_app.py`) that shares this project's
database, models and services. Everything else - the learner portal, activities, progress, admin,
H5P upload/validate/publish - runs in Streamlit with no companion.

## How identity flows

```
LTI 1.3 (production):
  LMS -> GET/POST  companion /lti/login     (OIDC initiation; state+nonce stored)
      -> 302 to the LMS authorize endpoint
  LMS -> POST      companion /lti/launch    (id_token form_post; validated vs JWKS, nonce, aud, deployment)
      -> companion mints a signed, single-use LAUNCH TOKEN
      -> 302 to  STREAMLIT_URL/?launch=<token>
  Streamlit verifies the launch token, consumes its jti once, upserts the learner and issues a
  signed session token it keeps in the URL (?s=) so refreshes stay signed in.

Signed-token fallback (no LTI, or local dev):
  The LMS (or tools/make_dev_link.py) mints the same signed launch token and links the learner to
  STREAMLIT_URL/?launch=<token>. Same validation path.
```

A raw `?dev=` parameter only works when `DEV_MODE=true`; it is a local convenience, never trusted
in production.

## Configuration

`.env` (both processes read it):
```
STREAMLIT_URL=https://lab.example.com
COMPANION_PUBLIC_URL=https://lab-companion.example.com
COMPANION_URL=https://lab-companion.example.com     # used by the learner UI to embed H5P
LAUNCH_TOKEN_SECRET=<shared secret, 32+ bytes>
LAUNCH_TOKEN_ISSUER=https://lms.example.com
LAUNCH_TOKEN_AUDIENCE=decision-lab

# LTI 1.3 (companion):
LTI_PLATFORM_ISSUER=https://lms.example.com
LTI_CLIENT_ID=<client id the LMS assigns this tool>
LTI_AUTH_LOGIN_URL=https://lms.example.com/mod/lti/auth.php
LTI_PLATFORM_JWKS_URL=https://lms.example.com/mod/lti/certs.php
LTI_DEPLOYMENT_ID=1
```

Register the tool in the LMS with:
- OIDC login URL: `COMPANION_PUBLIC_URL/lti/login`
- Redirect URI:  `COMPANION_PUBLIC_URL/lti/launch`
- Deep-link an activity by pointing its `target_link_uri` at `...?mission=<activity code>`.

Run both:
```
streamlit run app.py                                       # learner + admin
uvicorn companion.lti_app:app --host 0.0.0.0 --port 8000   # LTI + H5P
```

## H5P playback + xAPI

- The admin creates an activity of type H5P and uploads a `.h5p` package (stored in the database as
  bytes; versions are immutable, published versions are never overwritten).
- On play, the learner UI embeds `h5p-standalone` pointed at the companion's
  `GET /h5p/play/<versionId>/<path>` (which streams package entries from the database).
- The H5P player emits xAPI statements; the embed POSTs each to the companion `POST /h5p/event`
  with the learner's signed session token. The companion verifies the token, normalises the xAPI
  (answered -> event; score raw/max -> score/percentage; completed -> completion) and writes it to
  the learner's attempt. This is the only path that stores a verified H5P score.

If you do not run the companion, H5P activities still appear and can be published, but a learner
opening one sees a notice that playback needs the companion. All other activity types (links,
embeds, videos, documents) need no companion.

## Note on the CDN

`h5p-standalone` loads from jsDelivr. If you enforce a strict CSP, allow `cdn.jsdelivr.net` for
scripts/styles, or vendor the library locally.
