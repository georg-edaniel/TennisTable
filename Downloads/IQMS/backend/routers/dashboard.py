"""Routes dashboard — données temps réel, historique, comparaison, recommandations."""
import re
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from core.database import get_influx_query_api, get_db
from core.security import get_current_user
from core.config import get_settings
from models.device import Device
from models.alert import Alert

router = APIRouter()
settings = get_settings()

# ── Niveaux AQI (standard EPA) ───────────────────────────────
AQI_LEVELS = [
    (0,   50,  "Bon",          "#22c55e", "Qualité de l'air satisfaisante"),
    (51,  100, "Modéré",       "#f59e0b", "Qualité acceptable"),
    (101, 150, "Mauvais",      "#f97316", "Mauvais pour les groupes sensibles"),
    (151, 200, "Très mauvais", "#ef4444", "Mauvais pour tout le monde"),
    (201, 300, "Dangereux",    "#8b5cf6", "Alerte sanitaire"),
    (301, 500, "Extrême",      "#7e0023", "Urgence sanitaire"),
]


def get_aqi_info(aqi: int) -> dict:
    for low, high, label, color, desc in AQI_LEVELS:
        if low <= aqi <= high:
            return {"level": label, "color": color, "description": desc}
    return {"level": "Inconnu", "color": "#9ca3af", "description": ""}


def get_recommendations(aqi: int, co_ppm: float, temperature: float,
                        humidity: float) -> list[dict]:
    """Génère des recommandations automatiques selon les seuils."""
    recs = []
    if aqi > 150:
        recs.append({"icon": "alert-triangle", "color": "red",
                     "title": "Qualité de l'air critique",
                     "text": "Ventilation immédiate recommandée. Réduisez les activités physiques intenses."})
    elif aqi > 100:
        recs.append({"icon": "wind", "color": "orange",
                     "title": "Qualité de l'air dégradée",
                     "text": "Ouvrez les fenêtres pour aérer la pièce. Vérifiez les sources de pollution."})
    elif aqi <= 50:
        recs.append({"icon": "check-circle", "color": "green",
                     "title": "Excellente qualité de l'air",
                     "text": "Les conditions sont optimales. Continuez à surveiller régulièrement."})

    if co_ppm > 9:
        recs.append({"icon": "alert-octagon", "color": "red",
                     "title": f"CO élevé : {co_ppm:.1f} ppm",
                     "text": "Seuil OMS dépassé (9 ppm). Aérez immédiatement et vérifiez les appareils à combustion."})
    elif co_ppm > 4:
        recs.append({"icon": "cloud", "color": "orange",
                     "title": f"CO modéré : {co_ppm:.1f} ppm",
                     "text": "Surveillance accrue recommandée. Vérifiez la ventilation de la pièce."})

    if temperature > 28:
        recs.append({"icon": "thermometer-sun", "color": "orange",
                     "title": f"Température élevée : {temperature:.1f}°C",
                     "text": "Activez la climatisation ou ouvrez les fenêtres pour rafraîchir la pièce."})
    elif temperature < 18:
        recs.append({"icon": "thermometer-snowflake", "color": "blue",
                     "title": f"Température basse : {temperature:.1f}°C",
                     "text": "Vérifiez le système de chauffage. Maintenez 18-22°C pour le confort."})

    if humidity > 70:
        recs.append({"icon": "droplets", "color": "blue",
                     "title": f"Humidité excessive : {humidity:.0f}%",
                     "text": "Risque de moisissures. Utilisez un déshumidificateur et améliorez la ventilation."})
    elif humidity < 30:
        recs.append({"icon": "droplet", "color": "yellow",
                     "title": f"Air trop sec : {humidity:.0f}%",
                     "text": "Utilisez un humidificateur. Maintenez 40-60% d'humidité relative."})

    return recs


# ── Dernières lectures ────────────────────────────────────────
@router.get("/latest")
async def get_latest_readings(
    device_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Dernières mesures de tous les capteurs depuis la DB (cache)."""
    query = select(Device).where(Device.is_active == True)
    if device_id:
        query = query.where(Device.device_id == device_id)
    result = await db.execute(query)
    devices = result.scalars().all()

    data = []
    for d in devices:
        aqi = d.last_aqi or 0
        info = get_aqi_info(aqi)
        data.append({
            "device_id":   d.device_id,
            "name":        d.name,
            "location":    d.location or "—",
            "building":    d.building,
            "floor":       d.floor,
            "room":        d.room,
            "lat":         d.lat,
            "lng":         d.lng,
            "is_online":   d.is_online,
            "last_seen":   d.last_seen.isoformat() if d.last_seen else None,
            "timestamp":   d.last_seen.isoformat() if d.last_seen else None,
            "aqi":         aqi,
            "aqi_info":    info,
            "co_ppm":      d.last_co_ppm or 0,
            "temperature": d.last_temperature or 0,
            "humidity":    d.last_humidity or 0,
            "lux":         d.last_lux or 0,
        })
    return {"count": len(data), "data": data}


# ── Historique InfluxDB ────────────────────────────────────────
@router.get("/history")
async def get_history(
    device_id: str = Query(...),
    start: str = Query("-24h"),
    field: str = Query("aqi"),
    current_user=Depends(get_current_user),
):
    """Historique d'un capteur sur une période donnée (depuis InfluxDB)."""
    query_api = get_influx_query_api()
    if not query_api:
        return {"device_id": device_id, "field": field, "start": start, "data": []}

    allowed_fields = {"co_ppm", "lux", "temperature", "humidity", "aqi", "temp_ds"}
    if field not in allowed_fields:
        raise HTTPException(status_code=400, detail=f"Champ invalide. Autorisés : {allowed_fields}")

    allowed_starts = {"-1h", "-24h", "-7d", "-30d"}
    if start not in allowed_starts:
        raise HTTPException(status_code=400, detail=f"Période invalide. Autorisées : {allowed_starts}")

    if not re.match(r'^[a-zA-Z0-9_\-]+$', device_id):
        raise HTTPException(status_code=400, detail="device_id invalide")

    # Granularité adaptée à la période
    window_map = {"-1h": "1m", "-24h": "5m", "-7d": "30m", "-30d": "2h"}
    window = window_map.get(start, "5m")

    flux_query = f"""
    from(bucket: "{settings.influx_bucket}")
      |> range(start: {start})
      |> filter(fn: (r) => r["_measurement"] == "air_quality")
      |> filter(fn: (r) => r["device_id"] == "{device_id}")
      |> filter(fn: (r) => r["_field"] == "{field}")
      |> aggregateWindow(every: {window}, fn: mean, createEmpty: false)
      |> yield(name: "mean")
    """
    try:
        tables = query_api.query(flux_query, org=settings.influx_org)
        data_points = [
            {"time": record.get_time().isoformat(), "value": record.get_value()}
            for table in tables for record in table.records
        ]
        return {"device_id": device_id, "field": field, "start": start, "data": data_points}
    except Exception:
        return {"device_id": device_id, "field": field, "start": start, "data": []}


# ── Comparaison des zones ─────────────────────────────────────
@router.get("/compare")
async def compare_zones(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Classement des zones par qualité de l'air (style BrainBox 'Compare Buildings')."""
    result = await db.execute(select(Device).where(Device.is_active == True))
    devices = result.scalars().all()

    zones = []
    for d in devices:
        aqi = d.last_aqi or 0
        info = get_aqi_info(aqi)
        # Score de qualité : 100 = parfait, 0 = critique
        score = max(0, 100 - aqi // 3)
        zones.append({
            "device_id":   d.device_id,
            "name":        d.name,
            "location":    d.location or d.device_id,
            "building":    d.building or "—",
            "floor":       d.floor or "—",
            "room":        d.room or "—",
            "is_online":   d.is_online,
            "aqi":         aqi,
            "aqi_label":   info["level"],
            "aqi_color":   info["color"],
            "co_ppm":      round(d.last_co_ppm or 0, 1),
            "temperature": round(d.last_temperature or 0, 1),
            "humidity":    round(d.last_humidity or 0, 1),
            "lux":         round(d.last_lux or 0, 0),
            "score":       score,
            "last_seen":   d.last_seen.isoformat() if d.last_seen else None,
        })

    # Trier du plus mauvais au meilleur AQI
    zones.sort(key=lambda z: z["aqi"], reverse=True)
    return {"count": len(zones), "zones": zones}


# ── Recommandations ───────────────────────────────────────────
@router.get("/recommendations")
async def get_recommendations_all(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Recommandations automatiques basées sur les dernières mesures."""
    result = await db.execute(
        select(Device).where(Device.is_active == True, Device.is_online == True)
    )
    devices = result.scalars().all()

    all_recs = []
    for d in devices:
        recs = get_recommendations(
            d.last_aqi or 0, d.last_co_ppm or 0,
            d.last_temperature or 20, d.last_humidity or 50
        )
        for r in recs:
            all_recs.append({**r, "device_id": d.device_id,
                             "device_name": d.name, "location": d.location or "—"})

    return {"count": len(all_recs), "recommendations": all_recs}


# ── Résumé global ─────────────────────────────────────────────
@router.get("/summary")
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    total = (await db.execute(select(func.count()).where(Device.is_active == True))).scalar()
    online = (await db.execute(
        select(func.count()).where(Device.is_active == True, Device.is_online == True)
    )).scalar()
    alerts = (await db.execute(select(func.count()).where(Alert.is_resolved == False))).scalar()

    result = await db.execute(select(Device).where(Device.is_active == True, Device.is_online == True))
    devices = result.scalars().all()
    avg_aqi = round(sum(d.last_aqi or 0 for d in devices) / max(len(devices), 1))

    return {
        "total_devices": total,
        "online_devices": online,
        "active_alerts": alerts,
        "avg_aqi": avg_aqi,
        "aqi_info": get_aqi_info(avg_aqi),
    }


# ── Résumé Net Zéro global ────────────────────────────────────
@router.get("/netzero")
async def get_netzero_summary(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Résumé Net Zéro complet (étapes BrainBox AI 02–10) :
    - émissions brutes (GHG inventory)
    - offsets actifs
    - émissions nettes
    - progression vers les objectifs
    - recommandations HVAC prioritaires
    """
    # Imports lazy pour éviter les imports circulaires
    from models.ghg import EnergyReading
    from models.offset import CarbonOffset, OffsetStatus
    from models.goal import EmissionGoal
    from services.ghg_service import aggregate_readings, hvac_recommendations
    from sqlalchemy import func

    # ── Émissions brutes ──────────────────────────────────────
    readings_result = await db.execute(select(EnergyReading))
    readings = readings_result.scalars().all()
    report = aggregate_readings(readings)
    gross_tco2e = round(report["emissions"]["total_kg"] / 1000.0, 6)

    # ── Offsets ───────────────────────────────────────────────
    offsets_result = await db.execute(
        select(func.coalesce(func.sum(CarbonOffset.quantity_tco2e), 0.0)).where(
            CarbonOffset.status.in_([OffsetStatus.ACTIVE, OffsetStatus.RETIRED])
        )
    )
    offset_tco2e = float(offsets_result.scalar())
    net_tco2e = round(gross_tco2e - offset_tco2e, 6)

    # ── Objectifs ─────────────────────────────────────────────
    goals_result = await db.execute(select(EmissionGoal))
    goals = goals_result.scalars().all()
    goals_summary = []
    for g in goals:
        reduction_needed = g.baseline_tco2e - g.target_tco2e
        reduction_achieved = g.baseline_tco2e - gross_tco2e
        pct = round(
            (reduction_achieved / reduction_needed * 100) if reduction_needed > 0 else 0.0, 1
        )
        goals_summary.append({
            "id":           g.id,
            "name":         g.name,
            "target_year":  g.target_year,
            "target_tco2e": g.target_tco2e,
            "progress_pct": pct,
            "on_track":     pct >= 0 and gross_tco2e <= g.baseline_tco2e,
        })

    # ── Recommandations HVAC (device le plus dégradé) ────────
    devices_result = await db.execute(
        select(Device).where(Device.is_active == True, Device.is_online == True)
    )
    online_devices = devices_result.scalars().all()
    worst = max(online_devices, key=lambda d: d.last_aqi or 0) if online_devices else None

    if worst:
        top_recs = hvac_recommendations(
            aqi=worst.last_aqi or 0,
            co_ppm=worst.last_co_ppm or 0.0,
            temperature=worst.last_temperature or 20.0,
            humidity=worst.last_humidity or 50.0,
        )[:3]
    else:
        top_recs = []

    return {
        "gross_emissions_tco2e": gross_tco2e,
        "total_offsets_tco2e":   round(offset_tco2e, 6),
        "net_emissions_tco2e":   net_tco2e,
        "is_net_zero":           net_tco2e <= 0,
        "coverage_pct":          round(
            (offset_tco2e / gross_tco2e * 100) if gross_tco2e > 0 else 0.0, 1
        ),
        "energy_readings_count": report["reading_count"],
        "goals":                 goals_summary,
        "top_hvac_recommendations": top_recs,
    }
