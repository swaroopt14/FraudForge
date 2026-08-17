"""SQLAlchemy engine. SQLite by default; Postgres via DATABASE_URL."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core import config
from app.data.schema import Base

_engine = None
_Session = None


def get_engine():
    global _engine, _Session
    if _engine is None:
        config.ensure_dirs()
        url = config.DATABASE_URL
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args)
        Base.metadata.create_all(_engine)
        _Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def session() -> Session:
    get_engine()
    assert _Session is not None
    return _Session()
