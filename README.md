# Decision Lab

A learning platform for two courses - PRINCE2 Foundation and PRINCE2 Practitioner - built with
Python and Streamlit. All content (course information, course guides, activities, guidelines, files
and links) is created and managed by an administrator. The application ships with no built-in
activities and never seeds any.

## Features

- Two courses: PRINCE2 Foundation and PRINCE2 Practitioner.
- Course guides (rich text and/or uploaded file), shown to learners before the activities.
- Flexible activities: uploaded H5P packages, H5P links, external quizzes, embedded activities,
  videos, documents and other approved links. New types can be added without a rebuild.
- Per-activity learner guidelines (text and an optional file).
- In-app viewing: PDFs, images and embeds render inside the app; downloads are a fallback only.
- Honest tracking: launch/access is always recorded; a score or completion is stored only when a
  trusted integration (xAPI / LTI 1.3 AGS) supplies it.
- Admin dashboard to manage courses, guides and activities with publish/unpublish and preview.
- Learner progress and a downloadable practice record (PDF).
- SQLite for local development, PostgreSQL for deployment.

## Technology

Python, Streamlit, SQLAlchemy, SQLite/PostgreSQL, and an optional FastAPI companion for H5P
playback (xAPI) and LTI 1.3.

## Run locally

Python 3.10-3.12 recommended.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env

python -m tools.create_admin     # uses ADMIN_EMAIL / ADMIN_PASSWORD from .env
streamlit run app.py
```

Open http://localhost:8501. Sign in as the admin ("Admin sign in") to add courses guides and
activities. Learners sign in with a self-declared email or through an LMS launch.

## Tests

```bash
pytest -q
```

## Documentation

- `docs/ADMIN-GUIDE.md` - how an admin creates guides and activities.
- `docs/SETUP.md` - install, configure and deploy.
- `docs/H5P-AND-LTI.md` - the optional companion service.
- `docs/RAILWAY.md` - deploying on Railway with PostgreSQL.
- `docs/TESTING.md` - tests performed and known limitations.
