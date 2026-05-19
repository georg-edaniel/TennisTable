"""Configuration pytest — fixtures partagées."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import patch, MagicMock

from main import app
from core.database import Base, get_db
from core.security import hash_password
from models.user import User

# Base de données SQLite en mémoire pour les tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Mock MQTT pour ne pas se connecter au broker pendant les tests
    with patch("core.mqtt_client.create_mqtt_client") as mock_mqtt:
        mock_mqtt.return_value = MagicMock()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session):
    user = User(
        username="testuser",
        email="test@aqims.local",
        hashed_password=hash_password("Password1!"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session):
    user = User(
        username="admin",
        email="admin@aqims.local",
        hashed_password=hash_password("Admin1234!"),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(client, test_user):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "Password1!"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(client, admin_user):
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "Admin1234!"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
