"""SQLAlchemy models.

Core tables: Learner, AdminUser, Course, CourseGuide, Activity, H5PVersion, MissionAttempt,
DecisionEvent, LearnerProgress, LaunchNonce, ActivityEvent, ActivityProgress, EmailOTP.
Enums are stored as strings for SQLite/PostgreSQL portability. The identity key
(issuer, externalLearnerId) is preserved exactly.

All content (courses, course guides, activities, guidelines, files and links) is admin-managed
and stored here. The application ships with no built-in activities and never seeds any.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def cuid() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.utcnow()


class Base(DeclarativeBase):
    pass


# Enum value sets (stored as plain strings).
LEVELS = ("FOUNDATION", "PRACTITIONER")
H5P_STATUSES = ("UPLOADED", "VALIDATED", "PUBLISHED", "UNPUBLISHED")
ATTEMPT_STATUSES = ("IN_PROGRESS", "COMPLETED")

# Activity types an admin can create. The model is open: new types can be added here and given a
# renderer in the learner launcher without changing the rest of the application.
ACTIVITY_TYPES = (
    "H5P",           # uploaded .h5p package, played in-app through the H5P runtime (companion)
    "H5P_LINK",      # a published H5P link / embed (e.g. H5P.com)
    "EXTERNAL_QUIZ", # external quiz or assessment link on another platform
    "EMBED",         # embedded activity from an approved provider (iframe)
    "VIDEO",         # a video resource (link or embed)
    "DOCUMENT",      # an uploaded document / file, shown in-app where the format allows
    "LINK",          # any other approved external learning resource
)
# Legacy value kept so old databases still read cleanly; it is not offered to admins.
LEGACY_ACTIVITY_TYPES = ("NATIVE",)
ACTIVITY_STATUSES = ("DRAFT", "PUBLISHED", "UNPUBLISHED", "ARCHIVED")
OPEN_MODES = ("NEW_TAB", "EMBED")
GUIDE_STATUSES = ("DRAFT", "PUBLISHED")
# Generic tracking event + progress vocab (for non-native/non-xAPI activities).
ACTIVITY_EVENT_TYPES = (
    "ACCESS", "LAUNCH", "VIEW", "START", "RESUME", "COMPLETE",
    "SUBMIT", "ABANDON", "ERROR", "SCORE",
)
COMPLETION_STATUSES = ("NOT_STARTED", "ACCESSED", "IN_PROGRESS", "COMPLETED")


class Learner(Base):
    __tablename__ = "learners"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    external_learner_id: Mapped[str] = mapped_column("externalLearnerId", String, nullable=False)
    issuer: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String)
    display_name: Mapped[str | None] = mapped_column("displayName", String)
    first_name: Mapped[str | None] = mapped_column("firstName", String)
    last_name: Mapped[str | None] = mapped_column("lastName", String)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=now)
    last_accessed_at: Mapped[datetime] = mapped_column("lastAccessedAt", DateTime, default=now)

    attempts: Mapped[list["MissionAttempt"]] = relationship(back_populates="learner", cascade="all, delete-orphan")
    progress: Mapped["LearnerProgress"] = relationship(back_populates="learner", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("issuer", "externalLearnerId", name="uq_learner_issuer_ext"),)


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column("passwordHash", String, nullable=False)
    display_name: Mapped[str | None] = mapped_column("displayName", String)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=now)
    last_login_at: Mapped[datetime | None] = mapped_column("lastLoginAt", DateTime)


class Course(Base):
    """One row per course (track). The two courses are PRINCE2 Foundation and PRINCE2 Practitioner.
    Editable course information lives here; the activity list and guide are separate, admin-managed
    records. Rows are created on demand, never seeded with sample content."""
    __tablename__ = "courses"
    code: Mapped[str] = mapped_column(String, primary_key=True)   # FOUNDATION | PRACTITIONER
    name: Mapped[str] = mapped_column(String, nullable=False)
    info: Mapped[str | None] = mapped_column(Text)               # short course information (optional)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, default=now, onupdate=now)


class CourseGuide(Base):
    """A course guide shown to learners before they start a course. A guide can carry rich text, an
    uploaded file (PDF/DOCX/...), or both. Stored persistently; never hardcoded."""
    __tablename__ = "course_guides"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    course_code: Mapped[str] = mapped_column("courseCode", String, nullable=False)  # FOUNDATION|PRACTITIONER
    title: Mapped[str | None] = mapped_column(String)
    body: Mapped[str | None] = mapped_column(Text)              # rich text / markdown
    file_name: Mapped[str | None] = mapped_column("fileName", String)
    file_bytes: Mapped[bytes | None] = mapped_column("fileBytes", LargeBinary)
    file_mime: Mapped[str | None] = mapped_column("fileMime", String)
    status: Mapped[str] = mapped_column(String, default="DRAFT")  # DRAFT | PUBLISHED
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, default=now, onupdate=now)
    published_at: Mapped[datetime | None] = mapped_column("publishedAt", DateTime)

    __table_args__ = (UniqueConstraint("courseCode", name="uq_course_guide_course"),)


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    code: Mapped[str] = mapped_column(String, nullable=False)          # e.g. I12
    track: Mapped[str] = mapped_column(String, nullable=False)         # FOUNDATION | PRACTITIONER
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    est_minutes: Mapped[str | None] = mapped_column("estMinutes", String)
    kind: Mapped[str] = mapped_column(String, default="NATIVE")        # NATIVE | H5P (legacy)
    available: Mapped[bool] = mapped_column(Boolean, default=False)
    order_index: Mapped[int] = mapped_column("orderIndex", Integer, default=0)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, default=now, onupdate=now)

    # ── Extended activity management (added) - all nullable/defaulted, backward compatible ──
    # Richer type vocabulary; `kind` is kept in sync (NATIVE/H5P) for the legacy code paths.
    activity_type: Mapped[str] = mapped_column("activityType", String, default="NATIVE")
    status: Mapped[str] = mapped_column(String, default="DRAFT")       # DRAFT|PUBLISHED|UNPUBLISHED|ARCHIVED
    url: Mapped[str | None] = mapped_column(String)                    # external launch URL (new tab)
    embed_url: Mapped[str | None] = mapped_column("embedUrl", String)  # iframe src (approved domains)
    open_mode: Mapped[str] = mapped_column("openMode", String, default="NEW_TAB")  # NEW_TAB|EMBED
    provider: Mapped[str | None] = mapped_column(String)              # e.g. H5P.COM, YOUTUBE, GENERIC
    instructions: Mapped[str | None] = mapped_column(Text)   # learner guidelines (rich text)
    # Optional supporting file for the guidelines (e.g. a worksheet or brief).
    guideline_file_name: Mapped[str | None] = mapped_column("guidelineFileName", String)
    guideline_file_bytes: Mapped[bytes | None] = mapped_column("guidelineFileBytes", LargeBinary)
    guideline_file_mime: Mapped[str | None] = mapped_column("guidelineFileMime", String)
    category: Mapped[str | None] = mapped_column(String)
    due_date: Mapped[datetime | None] = mapped_column("dueDate", DateTime)
    pass_mark: Mapped[int | None] = mapped_column("passMark", Integer)   # percent, optional
    max_points: Mapped[int | None] = mapped_column("maxPoints", Integer) # activity-level max score
    file_name: Mapped[str | None] = mapped_column("fileName", String)    # uploaded DOCUMENT name
    file_bytes: Mapped[bytes | None] = mapped_column("fileBytes", LargeBinary)  # uploaded DOCUMENT bytes
    file_mime: Mapped[str | None] = mapped_column("fileMime", String)
    managed: Mapped[bool] = mapped_column(Boolean, default=False)        # True = admin-created (not seeded)

    versions: Mapped[list["H5PVersion"]] = relationship(back_populates="activity", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("code", "track", name="uq_activity_code_track"),
        Index("ix_activity_track_order", "track", "orderIndex"),
    )


class H5PVersion(Base):
    __tablename__ = "h5p_versions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    activity_id: Mapped[str] = mapped_column("activityId", ForeignKey("activities.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, default="UPLOADED")
    file_name: Mapped[str] = mapped_column("fileName", String, nullable=False)
    file_size: Mapped[int] = mapped_column("fileSize", Integer, nullable=False)
    file_bytes: Mapped[bytes] = mapped_column("fileBytes", LargeBinary, nullable=False)
    title: Mapped[str | None] = mapped_column(String)
    main_library: Mapped[str | None] = mapped_column("mainLibrary", String)
    h5p_json: Mapped[dict | None] = mapped_column("h5pJson", JSON)
    validation: Mapped[str | None] = mapped_column(String)
    uploaded_by_id: Mapped[str | None] = mapped_column("uploadedById", ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=now)
    published_at: Mapped[datetime | None] = mapped_column("publishedAt", DateTime)

    activity: Mapped["Activity"] = relationship(back_populates="versions")

    __table_args__ = (UniqueConstraint("activityId", "version", name="uq_h5p_activity_version"),)


class MissionAttempt(Base):
    __tablename__ = "mission_attempts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    learner_id: Mapped[str] = mapped_column("learnerId", ForeignKey("learners.id", ondelete="CASCADE"))
    mission_id: Mapped[str] = mapped_column("missionId", String, nullable=False)  # activity code
    level: Mapped[str] = mapped_column(String, nullable=False)
    attempt_number: Mapped[int] = mapped_column("attemptNumber", Integer, default=1)
    score: Mapped[int] = mapped_column(Integer, default=0)
    max_score: Mapped[int] = mapped_column("maxScore", Integer, default=2)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    first_time_aligned: Mapped[bool] = mapped_column("firstTimeAligned", Boolean, default=False)
    repaired: Mapped[bool] = mapped_column(Boolean, default=False)
    red_line_hit: Mapped[bool] = mapped_column("redLineHit", Boolean, default=False)
    route_code: Mapped[str | None] = mapped_column("routeCode", String)
    feedback_tags: Mapped[list | None] = mapped_column("feedbackTags", JSON, default=list)
    first_attempt_score: Mapped[int | None] = mapped_column("firstAttemptScore", Integer)
    repaired_score: Mapped[int | None] = mapped_column("repairedScore", Integer)
    percentage: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="IN_PROGRESS")
    h5p_version_id: Mapped[str | None] = mapped_column("h5pVersionId", String)
    resume_state: Mapped[dict | None] = mapped_column("resumeState", JSON)
    started_at: Mapped[datetime] = mapped_column("startedAt", DateTime, default=now)
    completed_at: Mapped[datetime | None] = mapped_column("completedAt", DateTime)
    last_accessed_at: Mapped[datetime] = mapped_column("lastAccessedAt", DateTime, default=now)

    learner: Mapped["Learner"] = relationship(back_populates="attempts")
    events: Mapped[list["DecisionEvent"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("learnerId", "missionId", "level", "attemptNumber", name="uq_attempt"),
        Index("ix_attempt_learner_mission_level", "learnerId", "missionId", "level"),
    )


class DecisionEvent(Base):
    __tablename__ = "decision_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    learner_id: Mapped[str] = mapped_column("learnerId", ForeignKey("learners.id", ondelete="CASCADE"))
    attempt_id: Mapped[str] = mapped_column("attemptId", ForeignKey("mission_attempts.id", ondelete="CASCADE"))
    mission_id: Mapped[str] = mapped_column("missionId", String, nullable=False)
    level: Mapped[str] = mapped_column(String, nullable=False)
    step: Mapped[str] = mapped_column(String, nullable=False)
    selected_option: Mapped[str] = mapped_column("selectedOption", String, nullable=False)
    score_change: Mapped[int] = mapped_column("scoreChange", Integer, default=0)
    red_line: Mapped[bool] = mapped_column("redLine", Boolean, default=False)
    is_correct: Mapped[bool | None] = mapped_column("isCorrect", Boolean)
    feedback_tag: Mapped[str | None] = mapped_column("feedbackTag", String)
    route_code: Mapped[str | None] = mapped_column("routeCode", String)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=now)

    attempt: Mapped["MissionAttempt"] = relationship(back_populates="events")

    __table_args__ = (Index("ix_event_attempt", "attemptId"),)


class LearnerProgress(Base):
    __tablename__ = "learner_progress"
    learner_id: Mapped[str] = mapped_column("learnerId", ForeignKey("learners.id", ondelete="CASCADE"), primary_key=True)
    completed_missions: Mapped[int] = mapped_column("completedMissions", Integer, default=0)
    attempted_missions: Mapped[int] = mapped_column("attemptedMissions", Integer, default=0)
    total_points: Mapped[int] = mapped_column("totalPoints", Integer, default=0)
    first_time_aligned: Mapped[int] = mapped_column("firstTimeAligned", Integer, default=0)
    repaired_count: Mapped[int] = mapped_column("repairedCount", Integer, default=0)
    red_line_hits: Mapped[int] = mapped_column("redLineHits", Integer, default=0)
    current_episode: Mapped[str | None] = mapped_column("currentEpisode", String)
    current_mission: Mapped[str | None] = mapped_column("currentMission", String)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, default=now, onupdate=now)

    learner: Mapped["Learner"] = relationship(back_populates="progress")


class LaunchNonce(Base):
    __tablename__ = "launch_nonces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    nonce: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    issuer: Mapped[str] = mapped_column(String, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column("usedAt", DateTime)
    expires_at: Mapped[datetime] = mapped_column("expiresAt", DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=now)


class ActivityEvent(Base):
    """Append-only log of everything genuinely observed for an activity: access, launch, view,
    start/resume/complete, submit, abandon, error, and (only from a trusted integration) score.

    `verified` distinguishes a score/completion confirmed by a real integration (xAPI/LTI-AGS)
    from a mere launch/access we observed ourselves. Never set verified=True for a plain link.
    """
    __tablename__ = "activity_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    learner_id: Mapped[str] = mapped_column("learnerId", ForeignKey("learners.id", ondelete="CASCADE"))
    activity_id: Mapped[str | None] = mapped_column("activityId", ForeignKey("activities.id", ondelete="SET NULL"))
    code: Mapped[str | None] = mapped_column(String)
    track: Mapped[str | None] = mapped_column(String)
    event_type: Mapped[str] = mapped_column("eventType", String, nullable=False)
    source: Mapped[str] = mapped_column(String, default="UI")      # UI | LTI | XAPI | AGS | ADMIN
    score: Mapped[float | None] = mapped_column(Integer)
    max_score: Mapped[float | None] = mapped_column("maxScore", Integer)
    success: Mapped[bool | None] = mapped_column(Boolean)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=now)

    __table_args__ = (
        Index("ix_actevent_learner_activity", "learnerId", "activityId"),
        Index("ix_actevent_activity", "activityId"),
        Index("ix_actevent_created", "createdAt"),
    )


class ActivityProgress(Base):
    """One row per (learner, activity): the durable rollup for NON-native activities (external
    links, embeds, videos, documents, H5P links). Native missions keep using MissionAttempt.

    Upserted so returning/refreshing a learner never creates duplicate rows; counts are incremented
    and timestamps advanced. Scores are stored only when a trusted integration supplied them, in
    which case `score_verified` is True.
    """
    __tablename__ = "activity_progress"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    learner_id: Mapped[str] = mapped_column("learnerId", ForeignKey("learners.id", ondelete="CASCADE"))
    activity_id: Mapped[str] = mapped_column("activityId", ForeignKey("activities.id", ondelete="CASCADE"))
    code: Mapped[str | None] = mapped_column(String)
    track: Mapped[str | None] = mapped_column(String)
    completion_status: Mapped[str] = mapped_column("completionStatus", String, default="NOT_STARTED")
    launch_count: Mapped[int] = mapped_column("launchCount", Integer, default=0)
    view_count: Mapped[int] = mapped_column("viewCount", Integer, default=0)
    attempt_count: Mapped[int] = mapped_column("attemptCount", Integer, default=0)
    best_score: Mapped[int | None] = mapped_column("bestScore", Integer)
    best_max_score: Mapped[int | None] = mapped_column("bestMaxScore", Integer)
    progress_pct: Mapped[int | None] = mapped_column("progressPct", Integer)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    score_verified: Mapped[bool] = mapped_column("scoreVerified", Boolean, default=False)
    time_spent_seconds: Mapped[int] = mapped_column("timeSpentSeconds", Integer, default=0)
    first_access_at: Mapped[datetime | None] = mapped_column("firstAccessAt", DateTime)
    last_access_at: Mapped[datetime | None] = mapped_column("lastAccessAt", DateTime)
    completed_at: Mapped[datetime | None] = mapped_column("completedAt", DateTime)
    updated_at: Mapped[datetime] = mapped_column("updatedAt", DateTime, default=now, onupdate=now)

    __table_args__ = (
        UniqueConstraint("learnerId", "activityId", name="uq_activity_progress"),
        Index("ix_actprog_learner", "learnerId"),
        Index("ix_actprog_activity", "activityId"),
    )


class EmailOTP(Base):
    """One-time codes for OPTIONAL verification of a fallback email (off unless a mail sender is
    configured and REQUIRE_EMAIL_VERIFICATION=true). The code is stored hashed, never in clear."""
    __tablename__ = "email_otps"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=cuid)
    email: Mapped[str] = mapped_column(String, nullable=False)
    code_hash: Mapped[str] = mapped_column("codeHash", String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column("expiresAt", DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column("consumedAt", DateTime)
    created_at: Mapped[datetime] = mapped_column("createdAt", DateTime, default=now)

    __table_args__ = (Index("ix_emailotp_email", "email"),)
