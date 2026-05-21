"""
============================================================
 AQIMS — Air Quality Index Monitoring System
 Backend FastAPI — Point d'entrée principal
============================================================
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from core.config import get_settings
from core.database import create_tables
from core.mqtt_client import create_mqtt_client, start_mqtt_background, set_ws_broadcast
from routers import auth, devices, dashboard, alerts, fota, pages, demo, admin
from routers import ghg, offsets, goals, zones

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()

# ── Rate Limiter ─────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Gestionnaire WebSocket ────────────────────────────────────
class WebSocketManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WebSocket connecté — {len(self.active)} client(s)")

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        disconnected = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.active.remove(ws)


ws_manager = WebSocketManager()


# ── Lifespan (startup / shutdown) ────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Démarrage AQIMS Backend...")

    await create_tables()
    logger.info("✅ Tables DB créées/vérifiées")

    # MQTT : optionnel — non-fatal si le broker est absent (dev local)
    mqtt_client = None
    try:
        set_ws_broadcast(ws_manager.broadcast)
        mqtt_client = create_mqtt_client()
        start_mqtt_background(mqtt_client, asyncio.get_running_loop())
    except Exception as e:
        logger.warning(f"⚠️  MQTT non disponible (dev local) : {e}")

    yield

    # Shutdown
    logger.info("🛑 Arrêt AQIMS Backend")
    if mqtt_client:
        try:
            mqtt_client.disconnect()
        except Exception:
            pass


# ── Application FastAPI ───────────────────────────────────────
app = FastAPI(
    title="AQIMS — Air Quality Index Monitoring System",
    description="Système de supervision de la qualité de l'air — API REST + WebSocket",
    version="1.0.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aqims.local"] if settings.app_env == "production" else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Fichiers statiques + templates
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Routeurs API ──────────────────────────────────────────────
app.include_router(auth.router,      prefix="/api/v1/auth",     tags=["Authentification"])
app.include_router(devices.router,   prefix="/api/v1/devices",  tags=["Appareils"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard",tags=["Dashboard"])
app.include_router(alerts.router,    prefix="/api/v1/alerts",   tags=["Alertes"])
app.include_router(fota.router,      prefix="/api/v1/fota",     tags=["FOTA"])
app.include_router(demo.router,      prefix="/api/v1/demo",     tags=["Demo"])
app.include_router(admin.router,     prefix="/api/v1/admin",    tags=["Administration"])
app.include_router(ghg.router,       prefix="/api/v1/ghg",      tags=["GHG"])
app.include_router(offsets.router,   prefix="/api/v1/offsets",  tags=["Offsets Carbone"])
app.include_router(goals.router,     prefix="/api/v1/goals",    tags=["Objectifs GES"])
app.include_router(zones.router,     prefix="/api/v1/zones",    tags=["Zones"])
app.include_router(pages.router,                                tags=["Pages"])


# ── WebSocket temps réel ──────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            # Garder la connexion ouverte, recevoir éventuellement des commandes
            data = await ws.receive_text()
            logger.debug(f"WS reçu : {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


# ── Endpoints utilitaires ─────────────────────────────────────
@app.get("/health", tags=["Système"])
async def health_check():
    return {"status": "ok", "service": "AQIMS Backend", "version": "1.0.0"}


@app.get("/", tags=["Système"])
async def root():
    return {"message": "AQIMS API — consultez /docs pour la documentation"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.app_port, reload=True)
