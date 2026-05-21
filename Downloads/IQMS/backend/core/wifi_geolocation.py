"""
Résolution de position via WiFi scanning → Mozilla Location Services (gratuit).

Aucun module GPS requis : l'ESP32 scanne les points d'accès visibles
et envoie leurs BSSIDs + RSSI dans le payload MQTT.

Payload MQTT attendu (champ additionnel) :
{
    "device_id": "esp32-001",
    "wifi": [
        {"bssid": "aa:bb:cc:dd:ee:ff", "signal": -65},
        {"bssid": "11:22:33:44:55:66", "signal": -72}
    ],
    "aqi": 45, ...
}

Précision typique : 10–100 m en milieu urbain/intérieur.
"""
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

_MLS_URL = "https://location.services.mozilla.com/v1/geolocate?key=geoclue"


async def resolve_wifi_location(wifi_list: list[dict]) -> Optional[tuple[float, float]]:
    """
    Estime les coordonnées GPS à partir d'une liste de points d'accès WiFi.

    Retourne (lat, lng) ou None si la résolution échoue.
    """
    if not wifi_list:
        return None

    access_points = [
        {
            "macAddress": ap["bssid"],
            "signalStrength": ap.get("signal", ap.get("rssi", -70)),
        }
        for ap in wifi_list
        if ap.get("bssid")
    ]
    if not access_points:
        return None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(_MLS_URL, json={"wifiAccessPoints": access_points})

        if r.status_code == 200:
            body = r.json()
            loc = body.get("location", {})
            lat, lng = loc.get("lat"), loc.get("lng")
            if lat is not None and lng is not None:
                acc = body.get("accuracy", "?")
                logger.info(f"📍 WiFi geolocation: {lat:.5f}, {lng:.5f} (±{acc} m)")
                return float(lat), float(lng)
        else:
            logger.warning(f"MLS API {r.status_code}: {r.text[:120]}")

    except Exception as exc:
        logger.warning(f"WiFi geolocation indisponible: {exc}")

    return None
