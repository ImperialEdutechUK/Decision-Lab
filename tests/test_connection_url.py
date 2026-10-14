"""DATABASE_URL normalization + the Railway private-host guard."""
import pytest

from database.connection import normalize_database_url, _guard_internal_host
from sqlalchemy.engine import make_url


def test_postgres_scheme_gets_psycopg_driver():
    assert normalize_database_url("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert normalize_database_url("postgresql://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"


def test_existing_driver_left_alone():
    assert normalize_database_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("postgresql+psycopg2://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
    assert normalize_database_url("sqlite:///x.db") == "sqlite:///x.db"


def test_blank_passthrough():
    assert normalize_database_url("") == ""


def test_internal_host_refused_when_not_on_railway(monkeypatch):
    import config as C
    monkeypatch.setattr(C.config, "ON_RAILWAY", False, raising=False)
    with pytest.raises(RuntimeError):
        _guard_internal_host(make_url("postgresql+psycopg://u:p@postgres.railway.internal:5432/railway"))


def test_internal_host_allowed_on_railway(monkeypatch):
    import config as C
    monkeypatch.setattr(C.config, "ON_RAILWAY", True, raising=False)
    _guard_internal_host(make_url("postgresql+psycopg://u:p@postgres.railway.internal:5432/railway"))
