"""TOTP (Time-based One-Time Password) service — Google Authenticator / Authy compatible."""
import base64
import io
import json
import secrets
from typing import List

import pyotp
import qrcode
from passlib.hash import bcrypt

from web.models.user import User

APP_NAME = "TT Tracker"
BACKUP_CODE_COUNT = 8


def generate_totp_secret() -> str:
    """Generate a new random TOTP secret (base32, compatible with Google Authenticator)."""
    return pyotp.random_base32()


def get_totp_uri(user: User, secret: str) -> str:
    """Return the otpauth:// URI for QR code generation."""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email or user.username,
        issuer_name=APP_NAME,
    )


def get_qr_code_base64(totp_uri: str) -> str:
    """Generate a QR code PNG and return it as base64-encoded string."""
    img = qrcode.make(totp_uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode()


def verify_totp_code(secret: str, code: str, valid_window: int = 1) -> bool:
    """Verify a 6-digit TOTP code. Accepts codes within ±valid_window time steps (30s each)."""
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=valid_window)


def generate_backup_codes() -> List[str]:
    """Generate BACKUP_CODE_COUNT random 8-character alphanumeric backup codes."""
    return [secrets.token_hex(4).upper() for _ in range(BACKUP_CODE_COUNT)]


def hash_backup_codes(codes: List[str]) -> str:
    """Hash and serialize backup codes to JSON for storage."""
    hashed = [bcrypt.hash(code) for code in codes]
    return json.dumps(hashed)


def verify_backup_code(user: User, code: str) -> bool:
    """Check if code matches any stored backup code. Consumes the code if valid."""
    code = code.strip().upper()
    try:
        hashed_list: List[str] = json.loads(user.totp_backup_codes or "[]")
    except (json.JSONDecodeError, TypeError):
        return False

    for i, hashed in enumerate(hashed_list):
        try:
            if bcrypt.verify(code, hashed):
                # Remove used code
                hashed_list.pop(i)
                user.totp_backup_codes = json.dumps(hashed_list)
                return True
        except Exception:
            continue
    return False
