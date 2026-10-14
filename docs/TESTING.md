# Testing report

Environment: Python 3.13, SQLite (local). Run with `pytest -q` (34 tests) plus the manual checks
below. The Streamlit app was booted headless and its health endpoint returned 200.

## Automated tests

`tests/` covers:
- Admin auth (correct/incorrect password), activity create/edit/publish/unpublish.
- URL validation: http rejected, embed host must be on the allowlist, YouTube embed accepted.
- Safe delete (no learner records) and archive-instead-of-delete when records exist.
- Activity reordering (move up/down).
- Rejecting the legacy NATIVE type for new activities.
- No activities are seeded; the two courses are exactly Foundation and Practitioner.
- Course guides: save text, draft hidden from learners, publish makes it visible, cannot publish an
  empty guide, guide file validation and round-trip.
- Activity guideline and document files: save/round-trip, filename sanitisation, disallowed types
  rejected.
- Learners see only published activities; unpublished detail is not reachable.
- Generic tracking: launch/access persisted without duplicate rows, verified-only scores, report
  rows + CSV reflect persisted data, incomplete report excludes completed.
- H5P: package validation, entry read with path-traversal blocked, xAPI normalisation, and the full
  admin create -> upload -> validate -> publish flow (activity becomes H5P + published).
- Email-fallback identity: validation, stable keying by email, unverified marking, OTP scaffold.
- DATABASE_URL normalisation and the Railway private-host guard.

## Manual checks performed

| # | Check | Result |
|---|---|---|
| 1 | App starts (`streamlit run app.py`), `/_stcore/health` = 200 | Pass |
| 2 | Admin login works; wrong password rejected | Pass |
| 3 | No public registration anywhere (learners use email/LMS; admin via CLI only) | Pass |
| 4 | Login page is minimal (brand, email, continue, admin sign-in) | Pass |
| 5 | Branding shows "Decision Lab" (title, top bar, PDF header) | Pass |
| 6 | No long-dash characters anywhere in the project | Pass |
| 7 | No built-in activities; none recreated at startup; safe cleanup of old seeded rows | Pass |
| 8 | Admin creates and publishes a course guide (text + file) | Pass |
| 9 | Learner sees the published guide before the activity list; draft is hidden | Pass |
| 10 | Admin uploads an H5P package; it validates and publishes | Pass |
| 11 | Admin adds H5P links and external activity URLs (https + allowlist enforced) | Pass |
| 12 | Admin uploads other document files (PDF shown inline to learners) | Pass |
| 13 | Admin adds optional guidelines (text + file); shown before the activity | Pass |
| 14 | Unpublished content hidden from learners | Pass |
| 15 | Tracking persists launch/access; reports + CSV reflect it | Pass |
| 16 | File upload validation: size limit, extension allowlist, filename sanitisation | Pass |

## Known limitations

- H5P playback (and xAPI-verified scores/completion) require the FastAPI companion
  (`companion/lti_app.py`) with `COMPANION_URL` set. The upload/validate/publish pipeline is tested;
  live in-browser playback and xAPI capture were not exercised in this environment because they need
  the companion running and a real H5P package. Without the companion, H5P activities show a clear
  notice; all other activity types work fully.
- LTI 1.3 launch requires the companion plus LMS registration; not exercised here.
- DOCX/PPTX/XLSX cannot be rendered natively in the browser; PDFs, images and text render inline and
  other formats fall back to a download. No score/completion is claimed for link/embed/video/document
  activities unless a trusted integration supplies it.
- Files are stored in the database; for very large media use an external store and link to it.
