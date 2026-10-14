# Decision Lab

A learning platform for two courses - PRINCE2 Foundation and PRINCE2 Practitioner - built with Python and Streamlit. All content (course information, course guides, activities, guidelines, files and links) is created and managed by an administrator. The application ships with no built-in activities and never seeds any.

**Live Application:** [Decision Lab](https://decision-lab.up.railway.app/)

**## Features**

- Two courses: PRINCE2 Foundation and PRINCE2 Practitioner.
- Course guides (rich text and/or uploaded file), shown to learners before the activities.
- Flexible activities: uploaded H5P packages, H5P links, external quizzes, embedded activities, videos, documents and other approved links. New types can be added without a rebuild.
- Per-activity learner guidelines (text and an optional file).
- In-app viewing: PDFs, images and supported embeds render inside the app; downloads are a fallback only.
- Honest tracking: launch/access is always recorded; a score or completion is stored only when a trusted integration (xAPI / LTI 1.3 AGS) supplies it.
- Admin dashboard to manage courses, guides and activities with publish/unpublish and preview.
- Learner progress and a downloadable practice record (PDF).
- SQLite for local development, PostgreSQL for deployment.

**## Technology**

Python, Streamlit, SQLAlchemy, SQLite/PostgreSQL, and an optional FastAPI companion for H5P playback (xAPI) and LTI 1.3.

**## Run locally**

Python 3.10-3.12 recommended.

**1. Clone the repository**

```bash
git clone https://github.com/ImperialEdutechUK/Decision-Lab.git
cd Decision-Lab
```

If you have already downloaded the project, open a terminal in the project folder instead.

**2. Create a virtual environment**

Windows CMD:

```cmd
python -m venv .venv
.venv\Scripts\activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**3. Install dependencies**

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**4. Configure environment variables**

Windows CMD:

```cmd
copy .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Edit `.env` and configure the required variables, including `ADMIN_EMAIL` and `ADMIN_PASSWORD`, according to the application's configuration.

**5. Create the administrator account**

```bash
python -m tools.create_admin
```

**6. Start the application**

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501).

Sign in using the **Admin sign in** option to add courses, course guides and activities. Learners can sign in with a self-declared email or through a supported LMS launch, depending on the configured integration.

**Note:** The `.env.example` file must exist in the repository for the environment setup command to work. If it is missing, create `.env` manually using the required settings documented in `docs/SETUP.md`.

Never commit your `.env` file, passwords, API keys or database credentials to GitHub.

**## Live Deployment**

The application is deployed on Railway.

**Live URL:** [https://decision-lab.up.railway.app/](https://decision-lab.up.railway.app/)

The deployed application should use PostgreSQL and the required environment variables configured in Railway.

See `docs/RAILWAY.md` for deployment instructions.

**## Tests**

Run the automated test suite from the project directory:

```bash
pytest -q
```

**## Documentation**

- `docs/ADMIN-GUIDE.md` - how an admin creates and manages course guides and activities.
- `docs/SETUP.md` - installation, configuration and deployment.
- `docs/H5P-AND-LTI.md` - the optional companion service and H5P/LTI integration.
- `docs/RAILWAY.md` - deploying on Railway with PostgreSQL.
- `docs/TESTING.md` - tests performed and known limitations.

**## Activity and Tracking**

Decision Lab does not automatically create sample activities or seed predefined learning content. Administrators manage the courses, guides and activities available to learners.

Activity launches and access are recorded. Scores and completion statuses are stored only when a supported, trusted integration provides the relevant results. Activities that do not report results through a supported integration may have access records without verified scores or completion statuses.
