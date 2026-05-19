"""
Connexions aux bases de données :
- PostgreSQL (SQLAlchemy async) en production / Docker
- SQLite (aiosqlite) en développement local  ← USE_SQLITE=true dans .env
- InfluxDB — données time-series des capteurs
"""
import logging
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Choix de la base de données ─────────────────────────────
_use_sqlite = settings.use_sqlite

if _use_sqlite:
    _DB_PATH = Path(__file__).parent.parent.parent / "aqims_dev.db"
    _DB_URL = f"sqlite+aiosqlite:///{_DB_PATH}"
    _ENGINE_KWARGS: dict = {"echo": False}
else:
    _DB_URL = settings.database_url
    _ENGINE_KWARGS = {
        "echo": (settings.app_env == "development"),
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    }

engine = create_async_engine(_DB_URL, **_ENGINE_KWARGS)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── InfluxDB (optionnel en dev local) ───────────────────────
try:
    from influxdb_client import InfluxDBClient
    from influxdb_client.client.write_api import SYNCHRONOUS
    _influx_available = True
except ImportError:
    _influx_available = False

_influx_client = None


def get_influx_client():
    global _influx_client
    if not _influx_available:
        return None
    if _influx_client is None:
        try:
            _influx_client = InfluxDBClient(
                url=settings.influx_host,
                token=settings.influx_token,
                org=settings.influx_org,
            )
        except Exception as e:
            logger.warning(f"⚠️  InfluxDB non disponible : {e}")
    return _influx_client


def get_influx_write_api():
    client = get_influx_client()
    return client.write_api(write_options=SYNCHRONOUS) if client else None


def get_influx_query_api():
    client = get_influx_client()
    return client.query_api() if client else None
