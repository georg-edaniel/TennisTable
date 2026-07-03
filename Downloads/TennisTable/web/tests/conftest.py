"""
Fixtures pytest :
- Base de données SQLite en mémoire (isolation totale entre tests)
- TestClient sans lifespan (évite MQTT bridge + alembic en production)
- Utilisateurs admin / joueur pré-créés
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from web.core.database import Base, get_db
from web.core.security import hash_password
from web.models.user import User
from web.models.racket import Racket

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_engine():
    # StaticPool : toutes les connexions partagent la même DB en mémoire
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def client(test_engine):
    """
    TestClient avec DB in-memory injectée.
    Pas de context-manager (lifespan=off) → pas d'MQTT, pas d'alembic en test.
    """
    TestSession = sessionmaker(bind=test_engine)

    def _override_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    from web.main import app
    from web.core.rate_limit import limiter
    app.dependency_overrides[get_db] = _override_db

    # Seed minimal dans la DB de test
    db = TestSession()
    _seed(db)
    db.close()

    # Reset rate-limiter storage so tests don't hit 429
    try:
        limiter._storage.reset()
    except Exception:
        pass

    # Pas de `with` → le lifespan (MQTT/alembic) ne tourne PAS pendant les tests
    c = TestClient(app, raise_server_exceptions=True)
    yield c

    app.dependency_overrides.clear()
    # Reset limiter again after the test
    try:
        limiter._storage.reset()
    except Exception:
        pass


def _seed(db):
    admin = User(
        username="admin",
        email="admin@test.local",
        password_hash=hash_password("admin123"),
        role="admin",
        display_name="Admin",
        is_active=True,
        must_change_password=False,
        onboarding_completed=True,
        elo_rating=1500.0,
        elo_matches=0,
        elo_wins=0,
        elo_last_change=0.0,
        subscription_tier="free",
    )
    player = User(
        username="joueur1",
        email="joueur1@test.local",
        password_hash=hash_password("pass1234"),
        role="player",
        display_name="Joueur 1",
        is_active=True,
        onboarding_completed=True,
        elo_rating=1500.0,
        elo_matches=0,
        elo_wins=0,
        elo_last_change=0.0,
        subscription_tier="free",
    )
    db.add_all([admin, player])
    db.flush()

    r1 = Racket(ble_device_name="TableTennisBat1", label="Raquette 1", assigned_to=player.id)
    r2 = Racket(ble_device_name="TableTennisBat2", label="Raquette 2")
    db.add_all([r1, r2])
    db.commit()


def login(client, username="admin", password="admin123") -> dict:
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()
