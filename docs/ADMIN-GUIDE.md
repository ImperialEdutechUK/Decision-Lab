# Admin guide - managing courses, guides and activities

Sign in with "Admin sign in" on the landing page, using the admin email and password created with
`python -m tools.create_admin`. Learners never see the admin area.

The admin dashboard has five tabs: Overview, Courses & guides, Activities, Learners, Reports.

## Create or edit a course guide

1. Go to Courses & guides and choose a course (PRINCE2 Foundation or PRINCE2 Practitioner).
2. Optional: add Course information shown to learners.
3. Course guide supports text, a file, or both:
   - Text: write Markdown (headings, lists, links) and Save guide text.
   - File: upload a PDF, DOCX, PPTX, TXT or HTML file, then Save file. Replace or Remove it anytime.
     PDFs, images and text render inside the app; other formats offer a download fallback.
4. Publish guide to make it visible to learners (Unpublish to hide it again). Learners see the
   published guide at the top of the course, before the activities.

## Add an activity

1. Go to Activities, choose a Type, and fill in the form.
2. Common fields: Title, Course, Short description, Guidelines text, optional Guidelines file,
   Estimated minutes, Pass mark, Status.
3. Type-specific fields:
   - H5P: upload an `.h5p` package. It is validated on upload; publish the activity to make the
     package's published version playable in-app (requires the companion, see H5P-AND-LTI.md).
   - H5P link / External quiz / Video / Link: choose Open mode (new tab or embed) and enter the
     https URL. For embeds, the host must be on the approved allowlist.
   - Embed: enter an https Embed URL from an approved provider (shown inline in an iframe).
   - Document: upload a file (PDF, DOCX, PPTX, XLSX, HTML, ...). PDFs, images and text show inline;
     an uploaded interactive HTML activity runs in-app inside a sandboxed iframe (its scripts run in
     an isolated origin, so it cannot access the application). Learners do not download to use it.
4. Create. New activities start as Draft unless you set Status to Published.

## Guidelines for learners

Guidelines are optional, per activity. Add guidelines text (Markdown) and, if useful, a supporting
file. Learners see the guidelines on the activity page before they open it. If there are no
guidelines, no guidelines section is shown.

## Manage activities

In Manage activity: Publish, Unpublish, Draft, Move up / Move down (ordering), Delete, Preview and
Edit. Delete removes an activity only when no learner records reference it; otherwise it is archived
so learner data is preserved. Learners only ever see Published activities.

## Reports

Filter by activity, course, status or learner, view records and Export CSV. Verified scores are
marked; "Tracking coverage" lists activity types for which only launch/access is recorded.
