"""FastAPI application — lifespan manages MQTT bridge + WebSocket manager."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

from web.core.config import settings
from web.core.database import db_context
from web.core.mqtt_bridge import MqttBridge
from web.core.ws_manager import WebSocketManager
from web.core.rate_limit import limiter
from web.models import User, Racket, Tournament, TournamentParticipant, TournamentMatch, UserBadge, WeeklyGoal, Challenge, Club, ClubMember  # noqa: F401
from web.models.password_reset import PasswordResetToken  # noqa: F401
from web.services.auth_service import create_admin_if_missing
from web.services.session_service import record_if_active

logger = logging.getLogger("main")

# ── Sentry (optional) ─────────────────────────────────────────────────────────
if settings.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)
    logger.info("Sentry initialized")

# ── Paths ────────────────────────────────────────────────────────────────────
_WEB_DIR = Path(__file__).parent
STATIC_DIR = _WEB_DIR / "static"
_TEMPLATES_DIR = _WEB_DIR / "templates"
_error_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ── DB init + seed ────────────────────────────────────────────────────────────
_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _init_db():
    """Create tables (fresh DB) or run migrations (existing DB), then seed."""
    from sqlalchemy import inspect as sa_inspect
    from web.core.database import Base, engine as _engine

    alembic_cfg = AlembicConfig(str(_ALEMBIC_INI))

    if not sa_inspect(_engine).has_table("users"):
        Base.metadata.create_all(_engine)
        alembic_command.stamp(alembic_cfg, "head")
        logger.info("Fresh DB — tables created and stamped at head")
    else:
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

    # Virtual racket for manual match entry (no BLE hardware required)
    if not db.query(Racket).filter(Racket.ble_device_name == "__manual__").first():
        db.add(Racket(ble_device_name="__manual__", label="Saisie manuelle"))

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
    loop = asyncio.get_running_loop()
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

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.web.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # Prevent browser from caching authenticated HTML pages — stops back-button bypass
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
        # CSP: allow same-origin + CDN scripts already used in templates
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net unpkg.com; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net fonts.googleapis.com; "
            "font-src 'self' fonts.gstatic.com data:; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none';"
        )
        # Only add HSTS on HTTPS responses
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return _error_templates.TemplateResponse(request, "404.html", {}, status_code=404)


@app.exception_handler(500)
async def server_error(request: Request, exc):
    return _error_templates.TemplateResponse(request, "500.html", {}, status_code=500)


from fastapi.responses import JSONResponse  # noqa: E402

@app.get("/health", tags=["system"])
async def health():
    return JSONResponse({"status": "ok", "app": "TT Tracker"})


# Routers
from web.routers import auth, users, rackets, sessions, analysis, ws, pages, leaderboard, tournaments  # noqa: E402
from web.routers import demo, stripe_router, push_router, badges, goals, challenges, clubs  # noqa: E402

# HTML pages first (path priority)
app.include_router(pages.router)
app.include_router(leaderboard.router)
app.include_router(tournaments.router)
app.include_router(demo.router)
app.include_router(stripe_router.router)

# Auth — no /api prefix
app.include_router(auth.router)

# REST API routes under /api prefix
app.include_router(users.router, prefix="/api")
app.include_router(rackets.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(leaderboard.api_router, prefix="/api")
app.include_router(tournaments.api_router, prefix="/api")
app.include_router(push_router.router, prefix="/api")
app.include_router(badges.router, prefix="/api")
app.include_router(goals.router, prefix="/api")
app.include_router(challenges.router, prefix="/api")
app.include_router(clubs.router)
app.include_router(clubs.api_router, prefix="/api")
app.include_router(ws.router)
