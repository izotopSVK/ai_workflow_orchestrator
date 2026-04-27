from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def init_engine(db_url: str) -> Engine:
    global _engine, _SessionLocal
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    _engine = create_engine(db_url, future=True, connect_args=connect_args)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Engine not initialized. Call init_engine() first.")
    return _engine


def get_session() -> Iterator[Session]:
    if _SessionLocal is None:
        raise RuntimeError("Session factory not initialized. Call init_engine() first.")
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def session_scope() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("Session factory not initialized. Call init_engine() first.")
    return _SessionLocal()
