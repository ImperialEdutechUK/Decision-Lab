# Activity tracking - what is and isn't tracked

Decision Lab is honest about the limits of tracking externally hosted content. Everything is
persisted in the database.

## Always recorded (observed by us)

For every activity type we record that a learner accessed and launched the activity, with
timestamps and counts. These are stored in `ActivityEvent` (append-only log) and rolled up into one
`ActivityProgress` row per (learner, activity). Returning or refreshing never creates duplicate
rows.

## Score and completion (only when verified)

A score or completion is stored only when a trusted integration supplies it:

- Uploaded H5P packages played through the companion: xAPI statements set a verified score and
  completion on the learner's attempt.
- LTI 1.3 Assignment and Grade Services (AGS): a hook exists in
  `services/tracking_service.record_verified_result`; wire your platform's AGS call to it.

For plain links, embeds, videos and documents there is no reliable way to receive a score from the
provider, so the learner record shows the score as "Not available". The admin Reports tab marks
verified scores explicitly and lists activities without verified score tracking under "Tracking
coverage".

## Summary by type

| Type | Opened in app | Launch/access tracked | Verified score/completion |
|---|---|---|---|
| H5P (uploaded) | yes (companion) | yes | yes (xAPI) |
| H5P link | embed or new tab | yes | only if the provider integration is configured |
| External quiz | embed or new tab | yes | no (unless AGS configured) |
| Embed | yes (iframe) | yes | no |
| Video | yes (iframe) or new tab | yes | no |
| Document | yes (inline viewer) | yes | no |
| Link | new tab | yes | no |
