"""FastAPI application — lifespan manages MQTT bridge + WebSocket manager."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

from web.core.config import settings
from web.core.database import db_context
from web.core.mqtt_bridge import MqttBridge
from web.core.ws_manager import WebSocketManager
from web.models import User, Racket  # noqa: F401 (ensure models imported before migrations)
from web.services.auth_service import create_admin_if_missing
from web.services.session_service import record_if_active

logger = logging.getLogger("main")

# ── Paths ────────────────────────────────────────────────────────────────────
_WEB_DIR = Path(__file__).parent
STATIC_DIR = _WEB_DIR / "static"
_TEMPLATES_DIR = _WEB_DIR / "templates"
_error_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ── DB init + seed ────────────────────────────────────────────────────────────
_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _init_db():
    """Run alembic migrations to head, then seed initial data."""
    alembic_cfg = AlembicConfig(str(_ALEMBIC_INI))
    alembic_command.upgrade(alembic_cfg, "head")
    logger.info("Alembic migrations applied")
    with db_context() as db:
        create_admin_if_missing(db)
        _sync_rackets_from_config(db)


def _sync_rackets_from_config(db):
    """Ensure devices from config.json exist in rackets table."""
    for dev in settings.devices:
        if not dev.device_name:
            continue
        existing = db.query(Racket).filter(
            Racket.ble_device_name == dev.device_name
        ).first()
        if not existing:
            r = Racket(
                ble_device_name=dev.device_name,
                label=dev.player_name or dev.device_name,
            )
            db.add(r)
    db.commit()


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB
    _init_db()
    logger.info("Database initialized")

    # WS manager
    ws_manager = WebSocketManager()
    app.state.ws_manager = ws_manager

    # MQTT bridge
    loop = asyncio.get_event_loop()
    bridge = MqttBridge(settings.mqtt, loop)

    async def _record(payload: dict):
        await record_if_active(payload, db_context)

    bridge.start()
    drain_task = asyncio.create_task(bridge.drain_loop(ws_manager, _record))

    logger.info("TT Tracker web server started → http://%s:%s", settings.web.host, settings.web.port)
    yield

    drain_task.cancel()
    bridge.stop()
    logger.info("Shutdown complete")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TT Tracker",
    description="TableTennis Web Application",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return _error_templates.TemplateResponse(request, "404.html", {}, status_code=404)


@app.exception_handler(500)
async def server_error(request: Request, exc):
    return _error_templates.TemplateResponse(request, "500.html", {}, status_code=500)

# Routers
from web.routers import auth, users, rackets, sessions, analysis, ws, pages, leaderboard  # noqa: E402

# HTML pages first (path priority)
app.include_router(pages.router)
app.include_router(leaderboard.router)

# Auth — no /api prefix (login.html uses /auth/login directly)
app.include_router(auth.router)

# REST API routes under /api prefix (avoids clashing with HTML page URLs)
app.include_router(users.router, prefix="/api")
app.include_router(rackets.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(leaderboard.api_router, prefix="/api")
app.include_router(ws.router)
