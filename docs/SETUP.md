# Setup

## Requirements

Python 3.10-3.12. PostgreSQL for deployment (SQLite is the zero-config local default).

## Install and run locally

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```

Edit `.env`:
- Leave `DATABASE_URL` blank to use a local SQLite file, or set it to your PostgreSQL URL.
- Set `SESSION_SECRET`, `ADMIN_SECRET`, `LAUNCH_TOKEN_SECRET` (generate with
  `python -c "import secrets;print(secrets.token_hex(32))"`).
- Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` for the first admin.

Create the first admin and start the app:

```bash
python -m tools.create_admin
streamlit run app.py
```

Open http://localhost:8501. "Admin sign in" opens the admin dashboard. With `DEV_MODE=true` you
can also launch as a sample learner, or continue with a self-declared email.

## Configure environment variables

See `.env.example` for every variable with inline notes, and `docs/RAILWAY.md` for the deployment
summary table. Key groups: database, signing secrets, learner identity, uploads, embedding safety,
and the optional H5P/LTI companion.

## Deploy

See `docs/RAILWAY.md`. In short: set the production variables (`APP_ENV=production`,
`DEV_MODE=false`, secrets, `DATABASE_URL`), deploy with the provided `Procfile`/`railway.json`,
and create the admin once from the host shell. Uploaded files persist in the database across
redeploys.

## Integration requirements (summary)

- H5P playback and verified scoring need the FastAPI companion (`companion/lti_app.py`) running with
  `COMPANION_URL` set on the app. Without it, other activity types work fully; H5P activities show a
  notice.
- LTI 1.3 launches need the companion plus the `LTI_*` variables and tool registration in the LMS.
- Embedding external content needs the host on `EMBED_ALLOWED_DOMAINS` (a sensible default list is
  built in); otherwise the activity opens in a new tab.
- No third-party credentials are stored in the app. Provide any provider keys via environment
  variables only.
