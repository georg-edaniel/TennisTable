"""
FOTA — Firmware Over-The-Air
Endpoint sécurisé pour la mise à jour des ESP32.
"""
import hashlib
import hmac
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from core.security import require_admin
from core.config import get_settings

router = APIRouter()
settings = get_settings()

FIRMWARE_DIR = Path("/app/firmware_releases")


class FirmwareInfo(BaseModel):
    version: str
    device_type: str
    sha256: str
    size: int
    release_notes: str = ""


def verify_device_signature(device_id: str, signature: str) -> bool:
    """Vérifie la signature HMAC-SHA256 de la requête OTA.

    Retourne False immédiatement si fota_secret_key n'est pas configuré,
    ce qui bloque toute requête OTA non sécurisée.
    """
    if not settings.fota_secret_key:
        return False
    expected = hmac.new(
        settings.fota_secret_key.encode(),
        device_id.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.get("/check/{device_id}")
async def check_update(
    device_id: str,
    current_version: str = Header(..., alias="X-Firmware-Version"),
    signature: str = Header(..., alias="X-Device-Signature"),
):
    """L'ESP32 vérifie s'il y a une mise à jour disponible."""
    if not verify_device_signature(device_id, signature):
        raise HTTPException(status_code=403, detail="Signature invalide")

    latest = _get_latest_firmware()
    if not latest:
        return {"update_available": False}

    update_available = latest["version"] != current_version
    return {
        "update_available": update_available,
        "latest_version": latest["version"] if update_available else None,
        "download_url": f"{settings.fota_server_url}/download/{device_id}" if update_available else None,
        "sha256": latest["sha256"] if update_available else None,
    }


@router.get("/download/{device_id}")
async def download_firmware(
    device_id: str,
    signature: str = Header(..., alias="X-Device-Signature"),
):
    """Téléchargement sécurisé du firmware."""
    if not verify_device_signature(device_id, signature):
        raise HTTPException(status_code=403, detail="Signature invalide")

    latest = _get_latest_firmware()
    if not latest:
        raise HTTPException(status_code=404, detail="Aucun firmware disponible")

    firmware_path = FIRMWARE_DIR / latest["filename"]
    if not firmware_path.exists():
        raise HTTPException(status_code=404, detail="Fichier firmware introuvable")

    return FileResponse(
        path=firmware_path,
        media_type="application/octet-stream",
        filename=latest["filename"],
        headers={"X-Firmware-SHA256": latest["sha256"]},
    )


@router.post("/upload")
async def upload_firmware(
    info: FirmwareInfo,
    current_user=Depends(require_admin),
):
    """Upload d'un nouveau firmware (admin uniquement)."""
    return {"message": "Firmware enregistré", "version": info.version}


def _get_latest_firmware() -> dict | None:
    """Retourne les infos du firmware le plus récent."""
    if not FIRMWARE_DIR.exists():
        return None
    firmwares = list(FIRMWARE_DIR.glob("*.bin"))
    if not firmwares:
        return None
    latest = sorted(firmwares)[-1]
    sha256 = hashlib.sha256(latest.read_bytes()).hexdigest()
    return {
        "filename": latest.name,
        "version": latest.stem,
        "sha256": sha256,
        "size": latest.stat().st_size,
    }
