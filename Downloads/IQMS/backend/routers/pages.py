"""
Routes HTML — pages du dashboard AQIMS.
Toutes les pages protégées vérifient le JWT dans le cookie de session.
Compatible Starlette 1.0.0 : TemplateResponse(request, name, context)
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_db
from models.user import User
from models.device import Device
from models.alert import Alert
from models.ghg import EnergyReading
from models.offset import CarbonOffset
from models.goal import EmissionGoal

router = APIRouter()
templates = Jinja2Templates(directory="templates")


async def _get_visible_devices(db: AsyncSession, user) -> list:
    """Devices visible to this user: admin sees all, others see only their own."""
    if user.is_admin:
        result = await db.execute(select(Device).where(Device.is_active == True))
    else:
        result = await db.execute(
            select(Device).where(Device.is_active == True, Device.owner_id == user.id)
        )
    return result.scalars().all()


def _get_token_from_cookie(request: Request) -> str | None:
    return request.cookies.get("access_token")


async def _get_user_from_cookie(request: Request, db: AsyncSession) -> User | None:
    token = _get_token_from_cookie(request)
    if not token:
        return None
    try:
        from core.security import decode_token
        payload = decode_token(token)
        user_id = payload.get("sub")
        result = await db.execute(select(User).where(User.id == int(user_id)))
        return result.scalar_one_or_none()
    except Exception:
        return None


# ── Pages publiques ───────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    # Starlette 1.0.0 : TemplateResponse(request, name, context)
    return templates.TemplateResponse(request, "login.html")


# ── Pages protégées ───────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    total_devices = (await db.execute(
        select(func.count()).where(Device.is_active == True)
    )).scalar()
    online_devices = (await db.execute(
        select(func.count()).where(Device.is_active == True, Device.is_online == True)
    )).scalar()
    active_alerts = (await db.execute(
        select(func.count()).where(Alert.is_resolved == False)
    )).scalar()

    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user,
        "stats": {
            "total_devices": total_devices,
            "online_devices": online_devices,
            "active_alerts": active_alerts,
        },
    })


@router.get("/devices", response_class=HTMLResponse)
async def devices_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    devices = await _get_visible_devices(db, user)

    # Résoudre les noms de propriétaires pour la vue admin
    owners: dict[int, str] = {}
    if user.is_admin:
        owner_ids = {d.owner_id for d in devices if d.owner_id}
        if owner_ids:
            ur = await db.execute(select(User).where(User.id.in_(owner_ids)))
            owners = {u.id: u.username for u in ur.scalars().all()}

    devices_json = [
        {
            "device_id": d.device_id,
            "name": d.name,
            "location": d.location or "",
            "building": d.building or "",
            "floor": d.floor,
            "room": d.room or "",
            "lat": d.lat,
            "lng": d.lng,
            "is_online": d.is_online,
            "firmware_version": d.firmware_version or "—",
            "last_seen": d.last_seen.strftime("%d/%m/%Y %H:%M") if d.last_seen else None,
            "last_aqi": d.last_aqi,
            "last_co_ppm": d.last_co_ppm,
            "last_temperature": d.last_temperature,
            "last_humidity": d.last_humidity,
            "last_lux": d.last_lux,
            "alert_co_threshold": d.alert_co_threshold,
            "alert_aqi_threshold": d.alert_aqi_threshold,
            "alert_temp_max": d.alert_temp_max,
            "alert_humidity_max": d.alert_humidity_max,
            "owner_username": owners.get(d.owner_id, "") if user.is_admin else "",
        }
        for d in devices
    ]

    return templates.TemplateResponse(request, "devices.html", {
        "user": user,
        "devices": devices,
        "devices_json": devices_json,
    })


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    result = await db.execute(
        select(Alert).order_by(Alert.created_at.desc()).limit(200)
    )
    alerts_orm = result.scalars().all()

    # Sérialisation explicite pour Jinja2 / tojson
    alerts_data = [
        {
            "id":          a.id,
            "device_id":   a.device_id,
            "type":        a.alert_type.value if a.alert_type else None,
            "level":       a.level.value if a.level else None,
            "message":     a.message,
            "value":       a.value,
            "threshold":   a.threshold,
            "is_resolved": a.is_resolved,
            "created_at":  a.created_at.isoformat() if a.created_at else None,
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        }
        for a in alerts_orm
    ]

    return templates.TemplateResponse(request, "alerts.html", {
        "user": user,
        "alerts": alerts_data,
    })


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    devices = await _get_visible_devices(db, user)
    return templates.TemplateResponse(request, "history.html", {"user": user, "devices": devices})


@router.get("/map", response_class=HTMLResponse)
async def map_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    devices = await _get_visible_devices(db, user)
    return templates.TemplateResponse(request, "map.html", {"user": user, "devices": devices})


@router.get("/compare", response_class=HTMLResponse)
async def compare_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    devices = await _get_visible_devices(db, user)
    return templates.TemplateResponse(request, "compare.html", {"user": user, "devices": devices})


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    devices = await _get_visible_devices(db, user)
    return templates.TemplateResponse(request, "reports.html", {"user": user, "devices": devices})


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "profile.html", {"user": user})


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(request, "admin.html", {"user": user})


@router.get("/ghg", response_class=HTMLResponse)
async def ghg_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    devices = await _get_visible_devices(db, user)
    devices_json = [
        {"device_id": d.device_id, "name": d.name, "building": d.building or ""}
        for d in devices
    ]
    return templates.TemplateResponse(request, "ghg.html", {
        "user": user,
        "devices": devices,
        "devices_json": devices_json,
    })


@router.get("/offsets", response_class=HTMLResponse)
async def offsets_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(request, "offsets.html", {"user": user})


@router.get("/goals", response_class=HTMLResponse)
async def goals_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _get_user_from_cookie(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    # Provide distinct buildings for the goal form dropdown
    result = await db.execute(
        select(Device.building).where(Device.building != None).distinct()
    )
    buildings = [row[0] for row in result.all()]
    return templates.TemplateResponse(request, "goals.html", {"user": user, "buildings": buildings})


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(request, "forgot_password.html")


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    token = request.query_params.get("token", "")
    return templates.TemplateResponse(request, "reset_password.html", {"token": token})


@router.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response
