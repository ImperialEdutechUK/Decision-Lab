"""Create tables (if missing) and apply in-place, additive migrations.

The application ships with NO built-in activities and never seeds any content. Courses, course
guides and activities are all created and managed by an administrator. Safe to call on every
startup: it never drops or overwrites existing data.
"""
from database.connection import engine
from database.models import Base
from database.migrations import run_migrations


def init_db():
    Base.metadata.create_all(engine)   # create any missing tables
    return run_migrations(engine)       # add new columns in place + one-time safe cleanup


if __name__ == "__main__":
    report = init_db()
    print(f"Database initialised and migrated. {report}")
