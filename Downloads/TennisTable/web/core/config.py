"""Reads config.json and environment variables, exposes settings for the web layer."""
import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv
load_dotenv()

# Locate config.json relative to this file (TennisTable/)
_BASE = Path(__file__).resolve().parents[2]
_CONFIG_FILE = _BASE / "config.json"


@dataclass
class MqttConfig:
    broker_host: str = "127.0.0.1"
    broker_port: int = 1883
    client_id: str = "tabletennis_web"
    keepalive: int = 60
    qos: int = 2
    topic_data: str = "tabletennis/data"
    topic_status: str = "tabletennis/system/status"


@dataclass
class EmailConfig:
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@tttracker.com"
    app_url: str = "http://localhost:8000"


@dataclass
class StripeConfig:
    secret_key: str = ""
    publishable_key: str = ""
    webhook_secret: str = ""
    price_club_id: str = ""


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    secret_file: str = str(_BASE / ".web_secret")
    db_url: str = f"sqlite:///{_BASE}/web/tennis.db"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    guest_token_expire_hours: int = 24
    allowed_origins: List[str] = field(default_factory=lambda: ["http://localhost:8000", "http://localhost:19006", "exp://localhost:8081"])


@dataclass
class DeviceConfig:
    device_name: str = ""
    player_name: str = ""
    cooldown_ms: int = 800


@dataclass
class AppConfig:
    mqtt: MqttConfig = field(default_factory=MqttConfig)
    web: WebConfig = field(default_factory=WebConfig)
    devices: List[DeviceConfig] = field(default_factory=list)
    email: EmailConfig = field(default_factory=EmailConfig)
    stripe: StripeConfig = field(default_factory=StripeConfig)
    sentry_dsn: str = ""


def load_config() -> AppConfig:
    cfg = AppConfig()

    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        m = raw.get("mqtt", {})
        cfg.mqtt = MqttConfig(
            broker_host=m.get("broker_host", cfg.mqtt.broker_host),
            broker_port=m.get("broker_port", cfg.mqtt.broker_port),
            client_id="tabletennis_web",
            keepalive=m.get("keepalive", cfg.mqtt.keepalive),
            qos=m.get("qos", cfg.mqtt.qos),
            topic_data=m.get("topic_data", cfg.mqtt.topic_data),
            topic_status=m.get("topic_status", cfg.mqtt.topic_status),
        )

        cfg.devices = [
            DeviceConfig(
                device_name=d.get("device_name", ""),
                player_name=d.get("player_name", ""),
                cooldown_ms=d.get("cooldown_ms", 800),
            )
            for d in raw.get("devices", [])
        ]

    # ENV overrides (take precedence over config.json)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        cfg.web.db_url = db_url

    allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
    if allowed_origins_env:
        cfg.web.allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

    cfg.email = EmailConfig(
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", "noreply@tttracker.com"),
        app_url=os.getenv("APP_URL", "http://localhost:8000"),
    )

    cfg.stripe = StripeConfig(
        secret_key=os.getenv("STRIPE_SECRET_KEY", ""),
        publishable_key=os.getenv("STRIPE_PUBLISHABLE_KEY", ""),
        webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", ""),
        price_club_id=os.getenv("STRIPE_PRICE_CLUB_ID", ""),
    )

    cfg.sentry_dsn = os.getenv("SENTRY_DSN", "")

    return cfg


# Singleton
settings = load_config()
