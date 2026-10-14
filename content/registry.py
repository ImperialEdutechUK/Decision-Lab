"""Course (track) metadata. This is the only fixed content in the application: the two courses.

Everything else - course information, guides, activities, guidelines, files and links - is created
and managed by an administrator and stored in the database. No activities are defined here.
"""

# The two courses. These are fixed identifiers; their editable information, guides and activities
# are stored in the database and managed through the admin dashboard.
TRACKS = {
    "FOUNDATION": {"code": "FOUNDATION", "name": "PRINCE2 Foundation"},
    "PRACTITIONER": {"code": "PRACTITIONER", "name": "PRINCE2 Practitioner"},
}
TRACK_CODES = list(TRACKS.keys())


def track_name(code):
    return TRACKS.get(code, {}).get("name", code)


def can_access_track(learner, track_code):
    """Every authenticated learner may open both courses. Replace with an LMS enrolment check
    later if needed - nothing else depends on the internals of this function."""
    return True
