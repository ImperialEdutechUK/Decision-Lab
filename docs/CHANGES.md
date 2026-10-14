# Change summary

This update turns the application into a clean, fully admin-managed Decision Lab with no built-in
activities and with course guides and flexible activity delivery. The existing stack (Python,
Streamlit, SQLAlchemy, SQLite/PostgreSQL, optional FastAPI companion), authentication and Railway
deployment are unchanged.

Main changes:

- Branding: the visible name is now "Decision Lab" everywhere (page title, top bar, PDF, companion),
  configurable via `APP_NAME`. Internal token/identifier defaults kept compatible.
- Login: a minimal landing page - brand, email sign-in (self-declared, as per the existing identity
  model), a developer launch in dev mode, and an "Admin sign in" with a show/hide password control.
  No public registration.
- Built-in activities removed: the sample branching missions and the activity catalogue seeding are
  gone. Startup no longer seeds anything. A one-time, safe migration removes previously-seeded sample
  activities that have no learner data, and archives (never deletes) any that do.
- Courses: PRINCE2 Foundation and PRINCE2 Practitioner remain, each with editable course
  information, a course guide and a published activity list - all admin-managed, nothing hardcoded.
- Course guides (new): per course, text and/or uploaded file, with create/edit/save/publish/
  unpublish/replace/delete. Learners see the published guide before the activities; PDFs render
  inline.
- Flexible activities: H5P upload, H5P link, external quiz, embed, video, document and link, with an
  open model that allows new types without a rebuild. Create/edit/publish/unpublish/reorder/delete,
  with validation, preview and clear status. H5P upload is validated and published in-app.
- Activity guidelines (new): optional per-activity text and an optional file, shown before the
  learner starts. No empty guidelines section is shown.
- In-app delivery: PDFs, images, text and approved embeds render inside the app; downloads are a
  fallback only. External links open in a new tab when embedding is not permitted.
- Storage and safety: uploaded files are stored in the database (persist across redeploys), with a
  size limit, an extension allowlist and filename sanitisation. Iframes are sandboxed and host-allow-
  listed; uploaded HTML is shown only in a locked-down sandbox. Learners can access published content
  only. The real `.env` (with secrets) is not shipped; `.env.example` holds placeholders.
- Text and typography: unnecessary descriptions, repeated explanations and decorative text removed
  across the UI; all long-dash characters replaced with normal hyphens.
- Tracking stays honest: launch/access is always recorded; a score/completion is stored only when a
  trusted integration (xAPI/LTI-AGS) supplies it.

See `README.md`, `docs/SETUP.md`, `docs/ADMIN-GUIDE.md`, `docs/ACTIVITY-TRACKING.md`,
`docs/H5P-AND-LTI.md`, `docs/RAILWAY.md` and `docs/TESTING.md`.
