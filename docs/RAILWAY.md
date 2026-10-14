# Deploying to Railway with PostgreSQL

Decision Lab is a Python/Streamlit application. It reuses an existing Railway PostgreSQL database -
it never creates another one and never drops or resets data. On startup it creates any missing
tables and applies small, additive, in-place migrations (new columns only), plus a one-time safe
cleanup of any previously-seeded sample activities. It never seeds new content.

Uploaded files (activity documents, course guides, guideline files, H5P packages) are stored in the
database, so they persist across redeploys. For very large media, prefer an external object store
and store only the link as an activity of type VIDEO/LINK/EMBED.

---

## 1. Local development

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```

Set `DATABASE_URL` to your Railway PUBLIC URL (Postgres service -> Variables ->
`DATABASE_PUBLIC_URL`). It looks like:

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@YOUR_HOST.proxy.rlwy.net:5432/railway
```

The app rewrites a legacy `postgres://` scheme to `postgresql+psycopg://`. Do not use the
`postgres.railway.internal` host locally - it only resolves inside Railway, and the app refuses it
with a clear message. If your network needs it, add `DB_SSLMODE=require`. Leaving `DATABASE_URL`
blank falls back to a local SQLite file.

```bash
python -m tools.create_admin     # reads ADMIN_EMAIL / ADMIN_PASSWORD from .env
streamlit run app.py
```

---

## 2. Deploy the Streamlit app

1. Push to a Git repo and New Project -> Deploy from GitHub (or `railway up`).
2. Add your existing Postgres to the project. Do not add a new one.
3. In the app service Variables, set:
   - `DATABASE_URL = ${{Postgres.DATABASE_URL}}` (private URL at runtime, never in Git)
   - `APP_ENV = production`
   - `DEV_MODE = false`
   - `SESSION_SECRET`, `ADMIN_SECRET`, `LAUNCH_TOKEN_SECRET` - 32+ random bytes each
     (`python -c "import secrets;print(secrets.token_hex(32))"`)
   - `ADMIN_EMAIL`, `ADMIN_PASSWORD` for the first admin (or run the command below)
   - Optional: `APP_NAME`, `ALLOW_EMAIL_IDENTITY`, `EMBED_ALLOWED_DOMAINS`, `LINK_ALLOWED_DOMAINS`,
     `MAX_UPLOAD_BYTES`, and the `LTI_*` / `COMPANION_URL` values if you use H5P/LTI.
4. `railway.json` / `Procfile` set the start command
   `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true` and
   the healthcheck path `/_stcore/health`.
5. First deploy auto-creates and migrates tables. Create the admin once from the Railway shell:
   `python -m tools.create_admin you@org.com 'a-strong-password' "Your Name"`.

---

## 3. (Optional) The LTI 1.3 + H5P companion as a second service

Deploy `companion/lti_app.py` as a second Railway service in the same project (same repo):

- Start command: `uvicorn companion.lti_app:app --host 0.0.0.0 --port $PORT`
- Same `DATABASE_URL` (`${{Postgres.DATABASE_URL}}`) and the same `LAUNCH_TOKEN_*` secrets.
- Set `STREAMLIT_URL` (public URL of the app service), `COMPANION_PUBLIC_URL` (this service's public
  URL), and on the app service `COMPANION_URL` to this service's public URL.

See `docs/H5P-AND-LTI.md` for LMS registration. Skip this if you do not use H5P/LTI.

---

## 4. Environment variables (summary)

| Variable | Where | Required | Notes |
|---|---|---|---|
| `DATABASE_URL` | app (+ companion) | yes | `${{Postgres.DATABASE_URL}}` on Railway; public `*.proxy.rlwy.net` URL locally |
| `APP_ENV` | app | yes | `production` on Railway |
| `DEV_MODE` | app | yes | `false` in production |
| `SESSION_SECRET` | app | yes | 32+ random bytes |
| `ADMIN_SECRET` | app | yes | 32+ random bytes |
| `LAUNCH_TOKEN_SECRET` | app (+ companion) | yes | 32+ random bytes; must match the companion |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | app | for setup | only for `tools.create_admin` |
| `APP_NAME` | app | optional | visible name (default "Decision Lab") |
| `MAX_UPLOAD_BYTES` | app | optional | general upload limit (default 25 MB) |
| `ALLOW_EMAIL_IDENTITY` | app | optional | default true - self-declared email sign-in |
| `EMBED_ALLOWED_DOMAINS` | app | optional | iframe allowlist (blank = sensible default) |
| `LINK_ALLOWED_DOMAINS` | app | optional | blank = allow any https link |
| `DB_SSLMODE` | app | optional | e.g. `require` for the public proxy |
| `COMPANION_URL` | app | optional | public URL of the companion (H5P) |
| `STREAMLIT_URL`, `COMPANION_PUBLIC_URL`, `LTI_*` | companion | optional | LTI 1.3 |

Never commit real secrets. `.gitignore` excludes `.env`, `*.db` and `.streamlit/secrets.toml`.
