"""
Client MQTT sécurisé (TLS mutuel + username/password + QoS=2).
Souscrit aux topics des capteurs et insère les données dans InfluxDB.
"""
import json
import math
import ssl
import logging
import asyncio
from datetime import datetime, timezone
from threading import Thread
import paho.mqtt.client as mqtt
from influxdb_client import Point
from .config import get_settings
from .database import get_influx_write_api

logger = logging.getLogger(__name__)
settings = get_settings()

# Seuil de détection de mouvement (mètres)
MOVE_THRESHOLD_M = 50


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance orthodromique en mètres entre deux points GPS."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Topics MQTT
TOPIC_SENSORS   = "aqims/sensors/#"
TOPIC_STATUS    = "aqims/status/#"
TOPIC_OTA_ACK   = "aqims/ota/+/status"

# Callback WebSocket (injectée depuis main.py)
_ws_broadcast_callback = None
# Référence à la boucle asyncio principale (injectée au démarrage)
_event_loop = None


def set_ws_broadcast(callback):
    global _ws_broadcast_callback
    _ws_broadcast_callback = callback


def _on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("✅ MQTT connecté au broker EMQX")
        client.subscribe(TOPIC_SENSORS,  qos=2)
        client.subscribe(TOPIC_STATUS,   qos=2)
        client.subscribe(TOPIC_OTA_ACK,  qos=1)
    else:
        logger.error(f"❌ MQTT connexion refusée : code {rc}")


def _on_disconnect(client, userdata, rc, properties=None, reason_code=None):
    logger.warning(f"⚠️  MQTT déconnecté (rc={rc}), tentative de reconnexion...")


def _on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        logger.debug(f"MQTT reçu [{msg.topic}] : {payload}")

        if msg.topic.startswith("aqims/sensors/"):
            _process_sensor_data(msg.topic, payload)
        elif msg.topic.startswith("aqims/status/"):
            _process_device_status(msg.topic, payload)
        elif "ota" in msg.topic:
            _process_ota_ack(msg.topic, payload)

    except json.JSONDecodeError:
        logger.error(f"❌ Payload MQTT non-JSON : {msg.payload}")
    except Exception as e:
        logger.error(f"❌ Erreur traitement message MQTT : {e}")


def _process_sensor_data(topic: str, payload: dict):
    """
    Insère les données capteurs dans InfluxDB + met à jour le cache Device en DB.
    Topic attendu : aqims/sensors/{device_id}
    Payload attendu (capteurs réels ESP32 ENUMA PCB) :
    {
        "device_id":       "esp32-001",
        "location":        "Salle-A101",
        "timestamp":       "2024-01-01T12:00:00Z",
        "temperature":     22.1,       <- DHT22 (ou temperature_dht)
        "humidity":        55.2,       <- DHT22
        "temperature_ds":  21.9,       <- DS18B20 (facultatif)
        "ldr_raw":         2048,       <- LDR brut ADC
        "lux":             320.0,      <- Lux estimé
        "mq7_raw":         1200,       <- MQ7 brut ADC
        "co_ppm":          3.5,        <- CO calculé (ppm)
        "aqi":             45,         <- AQI calculé
        "lat":             46.0878,    <- GPS direct (optionnel, si module NEO-6M)
        "lng":             -64.7782,   <- GPS direct (optionnel)
        "wifi": [                      <- WiFi scan pour géoloc sans GPS (optionnel)
            {"bssid": "aa:bb:cc:dd:ee:ff", "signal": -65},
            {"bssid": "11:22:33:44:55:66", "signal": -72}
        ]
    }
    """
    device_id = payload.get("device_id") or topic.split("/")[-1]
    location = payload.get("location", "unknown")

    # Normalisation des champs de température (DHT22 ou temperature_dht)
    temperature = float(
        payload.get("temperature") or
        payload.get("temperature_dht") or 0
    )
    humidity   = float(payload.get("humidity", 0))
    co_ppm     = float(payload.get("co_ppm", 0))
    lux        = float(payload.get("lux", 0))
    aqi        = int(payload.get("aqi", 0))

    # Position — priorité : GPS direct > WiFi scanning > Zone statique
    lat       = payload.get("lat") or payload.get("latitude")
    lng       = payload.get("lng") or payload.get("longitude")
    wifi_list = payload.get("wifi", [])
    zone_name = payload.get("zone")

    write_api = get_influx_write_api()
    point = (
        Point("air_quality")
        .tag("device_id", device_id)
        .tag("location", location)
        .field("temperature", temperature)
        .field("humidity",    humidity)
        .field("co_ppm",      co_ppm)
        .field("lux",         lux)
        .field("ldr_raw",     int(payload.get("ldr_raw", 0)))
        .field("mq7_raw",     int(payload.get("mq7_raw", 0)))
        .field("temp_ds",     float(payload.get("temperature_ds", temperature)))
        .field("aqi",         aqi)
        .time(payload.get("timestamp", datetime.now(timezone.utc).isoformat()))
    )
    write_api.write(bucket=settings.influx_bucket, org=settings.influx_org, record=point)

    # Mise à jour du cache (résolution : GPS > WiFi > Zone statique)
    _update_device_cache(device_id, location, aqi, co_ppm, temperature, humidity, lux,
                         lat, lng, wifi_list, zone_name)

    # Données enrichies pour le WebSocket
    enriched = {**payload, "device_id": device_id, "temperature": temperature,
                "humidity": humidity, "co_ppm": co_ppm, "lux": lux, "aqi": aqi}

    # Diffusion temps réel aux clients WebSocket
    if _ws_broadcast_callback and _event_loop:
        asyncio.run_coroutine_threadsafe(
            _ws_broadcast_callback({"type": "sensor_data", "data": enriched}),
            _event_loop,
        )


def _update_device_cache(device_id: str, location: str, aqi: int,
                          co_ppm: float, temperature: float, humidity: float, lux: float,
                          lat=None, lng=None, wifi_list: list | None = None,
                          zone_name: str | None = None):
    """Met à jour le cache des dernières mesures + génère les alertes si seuils dépassés.
    Résout la position selon la priorité : GPS direct > WiFi scanning > Zone statique."""
    try:
        from sqlalchemy import update as _update, select as _select
        from core.database import AsyncSessionLocal
        from models.device import Device
        from models.zone import Zone
        from core.wifi_geolocation import resolve_wifi_location

        async def _do_update():
            # ── Résolution de position (GPS > WiFi > Zone) ──────────
            resolved_lat, resolved_lng = lat, lng

            if not resolved_lat and wifi_list:
                result = await resolve_wifi_location(wifi_list)
                if result:
                    resolved_lat, resolved_lng = result

            if not resolved_lat and zone_name:
                async with AsyncSessionLocal() as zone_session:
                    zr = await zone_session.execute(
                        _select(Zone).where(Zone.name == zone_name)
                    )
                    zone = zr.scalar_one_or_none()
                    if zone:
                        resolved_lat, resolved_lng = zone.lat, zone.lng
                        logger.info(
                            f"📍 Zone '{zone_name}': {resolved_lat:.5f}, {resolved_lng:.5f}"
                        )

            # ── Mise à jour cache DB ────────────────────────────────
            update_values = dict(
                is_online=True,
                last_seen=datetime.now(timezone.utc),
                last_aqi=aqi,
                last_co_ppm=co_ppm,
                last_temperature=temperature,
                last_humidity=humidity,
                last_lux=lux,
                location=location,
            )
            if resolved_lat is not None and resolved_lng is not None:
                update_values["lat"] = resolved_lat
                update_values["lng"]  = resolved_lng

            moved_dist: float | None = None

            async with AsyncSessionLocal() as session:
                # Lire l'appareil AVANT la mise à jour (ancienne position + seuils)
                res = await session.execute(
                    _select(Device).where(Device.device_id == device_id)
                )
                device = res.scalar_one_or_none()

                # Détection de mouvement
                if (device and resolved_lat is not None
                        and device.lat is not None and device.lng is not None):
                    dist = _haversine_m(device.lat, device.lng, resolved_lat, resolved_lng)
                    if dist >= MOVE_THRESHOLD_M:
                        moved_dist = dist

                # Mise à jour des champs
                await session.execute(
                    _update(Device)
                    .where(Device.device_id == device_id)
                    .values(**update_values)
                )

                if device:
                    await _check_and_create_alerts(
                        session, device, aqi, co_ppm, temperature, humidity
                    )
                    if moved_dist is not None:
                        from models.alert import Alert, AlertType, AlertLevel
                        session.add(Alert(
                            device_id=device_id,
                            alert_type=AlertType.DEVICE_MOVED,
                            level=AlertLevel.INFO,
                            message=(
                                f"Appareil déplacé de {moved_dist:.0f} m "
                                f"(seuil {MOVE_THRESHOLD_M} m)"
                            ),
                            value=moved_dist,
                            threshold=float(MOVE_THRESHOLD_M),
                        ))
                        logger.info(
                            f"📍 Mouvement détecté [{device_id}] : "
                            f"{moved_dist:.0f} m"
                        )

                await session.commit()

            # ── Diffusion position mise à jour → carte temps réel ───
            if resolved_lat is not None and _ws_broadcast_callback:
                await _ws_broadcast_callback({
                    "type": "location_update",
                    "data": {
                        "device_id": device_id,
                        "lat": resolved_lat,
                        "lng": resolved_lng,
                    },
                })

            # ── Diffusion mouvement détecté ─────────────────────────
            if moved_dist is not None and _ws_broadcast_callback:
                await _ws_broadcast_callback({
                    "type": "device_moved",
                    "data": {
                        "device_id": device_id,
                        "distance_m": round(moved_dist),
                        "lat": resolved_lat,
                        "lng": resolved_lng,
                    },
                })

        if _event_loop:
            asyncio.run_coroutine_threadsafe(_do_update(), _event_loop)
    except Exception as e:
        logger.debug(f"Cache device non mis à jour (normal en dev sans DB) : {e}")


async def _check_and_create_alerts(session, device, aqi, co_ppm, temperature, humidity):
    """Crée une alerte si un seuil est dépassé — évite les doublons actifs."""
    from models.alert import Alert, AlertType, AlertLevel
    from sqlalchemy import select as _select

    checks = [
        (aqi > device.alert_aqi_threshold,
         AlertType.AQI_HIGH, AlertLevel.CRITICAL if aqi > 150 else AlertLevel.WARNING,
         f"AQI élevé : {aqi} (seuil {device.alert_aqi_threshold})", aqi, device.alert_aqi_threshold),

        (co_ppm > device.alert_co_threshold,
         AlertType.CO_HIGH, AlertLevel.CRITICAL if co_ppm > 15 else AlertLevel.WARNING,
         f"CO élevé : {co_ppm:.1f} ppm (seuil OMS {device.alert_co_threshold} ppm)", co_ppm, device.alert_co_threshold),

        (temperature > device.alert_temp_max,
         AlertType.TEMP_HIGH, AlertLevel.WARNING,
         f"Température élevée : {temperature:.1f}°C (seuil {device.alert_temp_max}°C)", temperature, device.alert_temp_max),

        (humidity > device.alert_humidity_max,
         AlertType.HUMIDITY_HIGH, AlertLevel.WARNING,
         f"Humidité excessive : {humidity:.0f}% (seuil {device.alert_humidity_max}%)", humidity, device.alert_humidity_max),
    ]

    for triggered, alert_type, level, message, value, threshold in checks:
        if not triggered:
            continue
        # Vérifier si une alerte non-résolue du même type existe déjà
        existing = await session.execute(
            _select(Alert).where(
                Alert.device_id == device.device_id,
                Alert.alert_type == alert_type,
                Alert.is_resolved == False,
            )
        )
        if existing.scalar_one_or_none():
            continue  # Alerte déjà active — pas de doublon

        new_alert = Alert(
            device_id=device.device_id,
            alert_type=alert_type,
            level=level,
            message=message,
            value=value,
            threshold=threshold,
        )
        session.add(new_alert)
        logger.warning(f"🚨 Alerte créée [{alert_type.value}] {device.device_id} : {message}")


def _process_device_status(topic: str, payload: dict):
    device_id = topic.split("/")[-1]
    logger.info(f"📡 Statut appareil {device_id} : {payload.get('status')}")


def _process_ota_ack(topic: str, payload: dict):
    device_id = topic.split("/")[2]
    status = payload.get("status")
    version = payload.get("version")
    logger.info(f"📦 OTA {device_id} : {status} (v{version})")


def create_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(
        client_id="aqims_backend",
        protocol=mqtt.MQTTv5,
    )

    # Authentification username/password
    client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

    # TLS mutuel (CA + certificat client + clé privée)
    tls_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    tls_ctx.load_verify_locations(cafile=settings.mqtt_ca_cert)
    tls_ctx.load_cert_chain(
        certfile=settings.mqtt_client_cert,
        keyfile=settings.mqtt_client_key,
    )
    tls_ctx.check_hostname = False  # hostname = "emqx" dans le container Docker
    client.tls_set_context(tls_ctx)

    # Callbacks
    client.on_connect    = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message    = _on_message

    return client


def start_mqtt_background(client: mqtt.Client, loop=None):
    """Lance le client MQTT dans un thread daemon.

    `loop` doit être la boucle asyncio principale (asyncio.get_running_loop()
    depuis un contexte async) pour que run_coroutine_threadsafe fonctionne
    correctement en Python 3.10+.
    """
    global _event_loop
    _event_loop = loop
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
    thread = Thread(target=client.loop_forever, daemon=True)
    thread.start()
    logger.info("🔌 Client MQTT démarré en arrière-plan")
    return thread
