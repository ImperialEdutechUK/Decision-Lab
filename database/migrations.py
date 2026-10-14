"""Lightweight, idempotent, backward-compatible schema migrations.

Why this exists
---------------
SQLAlchemy's ``create_all()`` creates missing TABLES but never alters an existing table, so adding
new columns to a database that already holds data needs an explicit step. These migrations:

* ADD the new ``activities`` columns in place (works on both PostgreSQL and SQLite),
* backfill sensible values for existing rows (``activityType`` from ``kind``, ``status`` from
  ``available``),

…and do all of it **without dropping, resetting or overwriting any existing row**. Safe to run on
every startup - each step checks the live schema first and is a no-op once applied.
"""
from sqlalchemy import inspect, text


# column_name -> SQL type by dialect. Column names are the DB names (camelCase) used in models.py.
_NEW_ACTIVITY_COLUMNS = {
    # No SQL DEFAULT on these two: we add them NULL on an existing table, then backfill from the
    # legacy `kind`/`available` columns below. (The ORM supplies values for all new inserts.)
    "activityType": {"postgresql": "VARCHAR", "sqlite": "VARCHAR"},
    "status": {"postgresql": "VARCHAR", "sqlite": "VARCHAR"},
    "url": {"postgresql": "VARCHAR", "sqlite": "VARCHAR"},
    "embedUrl": {"postgresql": "VARCHAR", "sqlite": "VARCHAR"},
    "openMode": {"postgresql": "VARCHAR", "sqlite": "VARCHAR", "default": "'NEW_TAB'"},
    "provider": {"postgresql": "VARCHAR", "sqlite": "VARCHAR"},
    "instructions": {"postgresql": "TEXT", "sqlite": "TEXT"},
    "category": {"postgresql": "VARCHAR", "sqlite": "VARCHAR"},
    "dueDate": {"postgresql": "TIMESTAMP", "sqlite": "TIMESTAMP"},
    "passMark": {"postgresql": "INTEGER", "sqlite": "INTEGER"},
    "maxPoints": {"postgresql": "INTEGER", "sqlite": "INTEGER"},
    "fileName": {"postgresql": "VARCHAR", "sqlite": "VARCHAR"},
    "fileBytes": {"postgresql": "BYTEA", "sqlite": "BLOB"},
    "fileMime": {"postgresql": "VARCHAR", "sqlite": "VARCHAR"},
    "managed": {"postgresql": "BOOLEAN", "sqlite": "BOOLEAN", "default": "FALSE"},
    # Optional supporting file attached to an activity's learner guidelines.
    "guidelineFileName": {"postgresql": "VARCHAR", "sqlite": "VARCHAR"},
    "guidelineFileBytes": {"postgresql": "BYTEA", "sqlite": "BLOB"},
    "guidelineFileMime": {"postgresql": "VARCHAR", "sqlite": "VARCHAR"},
}


def _dialect(engine) -> str:
    return engine.dialect.name  # 'postgresql' | 'sqlite' | ...


def _add_missing_columns(engine, table: str, specs: dict) -> list[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return []  # create_all() will build it fresh with every column
    existing = {c["name"] for c in insp.get_columns(table)}
    dialect = _dialect(engine)
    added = []
    with engine.begin() as conn:
        for col, spec in specs.items():
            if col in existing:
                continue
            sql_type = spec.get(dialect) or spec.get("postgresql") or "VARCHAR"
            ddl = f'ALTER TABLE {table} ADD COLUMN "{col}" {sql_type}'
            if "default" in spec:
                ddl += f' DEFAULT {spec["default"]}'
            conn.execute(text(ddl))
            added.append(col)
    return added


def _backfill_activity_rows(engine) -> None:
    """Populate the new columns for rows that pre-date them. Only touches NULL/placeholder values."""
    insp = inspect(engine)
    if "activities" not in insp.get_table_names():
        return
    with engine.begin() as conn:
        # activityType mirrors the legacy kind (NATIVE/H5P) where not yet set.
        conn.execute(text('UPDATE activities SET "activityType" = kind '
                          'WHERE ("activityType" IS NULL OR "activityType" = \'\') AND kind IS NOT NULL'))
        conn.execute(text('UPDATE activities SET "activityType" = \'NATIVE\' '
                          'WHERE "activityType" IS NULL OR "activityType" = \'\''))
        # status: anything currently available is treated as PUBLISHED; the rest stay DRAFT.
        conn.execute(text("UPDATE activities SET status = 'PUBLISHED' "
                          "WHERE (status IS NULL OR status = '') AND available = TRUE"))
        conn.execute(text("UPDATE activities SET status = 'DRAFT' "
                          "WHERE status IS NULL OR status = ''"))
        conn.execute(text('UPDATE activities SET "openMode" = \'NEW_TAB\' WHERE "openMode" IS NULL'))


def cleanup_builtin_activities(engine) -> int:
    """Remove previously-seeded built-in (sample) activities in a safe, one-time way.

    A row is removed only when it is NOT admin-managed AND no learner data references it (no mission
    attempts for its code/track, and no activity progress or events). Rows that hold learner data are
    kept (archived) so production records are never lost. Admin-created activities are never touched.
    """
    insp = inspect(engine)
    if "activities" not in insp.get_table_names():
        return 0
    cols = {c["name"] for c in insp.get_columns("activities")}
    if "managed" not in cols:
        return 0

    removed = 0
    with engine.begin() as conn:
        rows = conn.execute(text(
            'SELECT id, code, track FROM activities '
            'WHERE managed IS NULL OR managed = FALSE'
        )).fetchall()
        for rid, code, track in rows:
            def _count(table, where, params):
                if table not in insp.get_table_names():
                    return 0
                return conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"), params).scalar() or 0

            refs = (
                _count("mission_attempts", '"missionId" = :code AND level = :track',
                       {"code": code, "track": track})
                + _count("activity_progress", '"activityId" = :id', {"id": rid})
                + _count("activity_events", '"activityId" = :id', {"id": rid})
            )
            if refs:
                # Keep the data; just make sure it is not shown to learners.
                conn.execute(text("UPDATE activities SET status = 'ARCHIVED', available = FALSE "
                                  "WHERE id = :id"), {"id": rid})
            else:
                conn.execute(text("DELETE FROM h5p_versions WHERE \"activityId\" = :id"), {"id": rid})
                conn.execute(text("DELETE FROM activities WHERE id = :id"), {"id": rid})
                removed += 1
    return removed


def run_migrations(engine) -> dict:
    """Apply in-place, additive migrations. Returns a small report (handy in logs)."""
    added = _add_missing_columns(engine, "activities", _NEW_ACTIVITY_COLUMNS)
    _backfill_activity_rows(engine)
    removed = cleanup_builtin_activities(engine)
    return {"activities_columns_added": added, "builtin_activities_removed": removed}
