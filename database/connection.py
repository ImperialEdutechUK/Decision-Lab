"""SQLAlchemy engine + session factory.

SQLite by default (zero-config local dev); point DATABASE_URL at PostgreSQL for production.
All database access is isolated here and in services/* so the UI never touches the engine directly.

Railway PostgreSQL notes
------------------------
* Railway provides DATABASE_URL automatically when a Postgres plugin is attached. It can arrive as
  a legacy ``postgres://`` URL; we normalise it to the SQLAlchemy + psycopg (v3) form
  ``postgresql+psycopg://``.
* Use the **public** connection URL (``...proxy.rlwy.net:PORT``) from your local Windows machine.
  Use the **internal** URL (``postgres.railway.internal``) only when the app itself runs inside the
  same Railway project. The private ``*.railway.internal`` host is NOT reachable from your laptop,
  so we refuse it early (with a clear message) when we detect we are not running on Railway.
* ``pool_pre_ping`` + ``pool_recycle`` keep connections healthy across Railway's idle/sleep cycles.
"""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from config import config


def normalize_database_url(raw: str) -> str:
    """Return a SQLAlchemy-ready URL.

    - ``postgres://``          -> ``postgresql+psycopg://``   (Railway/Heroku legacy scheme)
    - ``postgresql://``        -> ``postgresql+psycopg://``   (add the psycopg v3 driver)
    - ``sqlite``/other         -> unchanged
    Already-qualified drivers (``postgresql+psycopg``, ``postgresql+psycopg2``, ...) are left alone.
    """
    url = (raw or "").strip()
    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        # only add a driver if none is specified
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _guard_internal_host(url_obj) -> None:
    """Refuse a *.railway.internal host when we are clearly not running inside Railway."""
    host = (url_obj.host or "").lower()
    if host.endswith(".railway.internal") and not config.ON_RAILWAY:
        raise RuntimeError(
            "DATABASE_URL points at the Railway PRIVATE host "
            f"'{host}', which is only reachable from inside Railway. For local development use the "
            "PUBLIC connection URL from your Railway Postgres service "
            "(Variables -> DATABASE_PUBLIC_URL, e.g. postgresql://...@<something>.proxy.rlwy.net:<port>/railway). "
            "Set that as DATABASE_URL in your local .env."
        )


def _build_engine():
    normalized = normalize_database_url(config.DATABASE_URL)
    url_obj = make_url(normalized)
    backend = url_obj.get_backend_name()  # 'sqlite' | 'postgresql' | ...

    connect_args = {}
    engine_kwargs = dict(echo=False, future=True)

    if backend == "sqlite":
        # allow use across Streamlit's threads
        connect_args["check_same_thread"] = False
    elif backend == "postgresql":
        _guard_internal_host(url_obj)
        # Optionally force sslmode (handy for the Railway public proxy from a local machine).
        if config.DB_SSLMODE and "sslmode" not in (url_obj.query or {}):
            connect_args["sslmode"] = config.DB_SSLMODE
        engine_kwargs.update(
            pool_pre_ping=True,
            pool_recycle=config.DB_POOL_RECYCLE,
            pool_size=config.DB_POOL_SIZE,
            max_overflow=config.DB_MAX_OVERFLOW,
        )

    return create_engine(normalized, connect_args=connect_args, **engine_kwargs)


engine = _build_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, expire_on_commit=False)


@contextmanager
def session_scope():
    """Transactional scope. Commits on success, rolls back on error, always closes."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
