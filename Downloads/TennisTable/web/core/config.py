"""Reads the existing config.json and exposes settings for the web layer."""
import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

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
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    secret_file: str = str(_BASE / ".web_secret")
    db_url: str = f"sqlite:///{_BASE}/web/tennis.db"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    guest_token_expire_hours: int = 24


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


def load_config() -> AppConfig:
    cfg = AppConfig()
    if not _CONFIG_FILE.exists():
        return cfg

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

    return cfg


# Singleton
settings = load_config()
