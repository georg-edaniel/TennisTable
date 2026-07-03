"""SQLAlchemy engine + session factory."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from contextlib import contextmanager
from .config import settings

_db_url = settings.web.db_url
_is_postgres = "postgresql" in _db_url

engine = create_engine(
    _db_url,
    connect_args={} if _is_postgres else {"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session and closes it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_context():
    """Context-manager version for use outside FastAPI (e.g. lifespan tasks)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
