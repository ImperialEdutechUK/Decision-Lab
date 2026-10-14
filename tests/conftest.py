import os
import tempfile

# Point the app at a throwaway SQLite DB BEFORE any app module imports the engine.
os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(suffix="_kdl_test.db")
os.environ["APP_ENV"] = "development"
os.environ["LAUNCH_TOKEN_SECRET"] = "test-secret"

import pytest  # noqa: E402
from database.init_db import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _db():
    init_db()
    yield
