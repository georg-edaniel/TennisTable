"""
Configuration centralisée — chargée depuis les variables d'environnement (.env).
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

# Cherche .env dans backend/ puis dans le répertoire parent (racine du projet)
_BASE = Path(__file__).parent.parent
_ENV_FILE = _BASE / ".env" if (_BASE / ".env").exists() else _BASE.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # Application
    app_env: str = "development"
    app_secret_key: str
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    use_sqlite: bool = False   # True = SQLite local, False = PostgreSQL (Docker/prod)

    # PostgreSQL
    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "aqims_db"
    db_user: str
    db_password: str

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # InfluxDB
    influx_host: str = "http://influxdb:8086"
    influx_org: str = "aqims"
    influx_bucket: str = "air_quality"
    influx_token: str

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"

    # MQTT
    mqtt_host: str = "emqx"
    mqtt_port: int = 8883
    mqtt_username: str = "backend_service"
    mqtt_password: str
    mqtt_ca_cert: str = "/app/certs/ca.crt"
    mqtt_client_cert: str = "/app/certs/client.crt"
    mqtt_client_key: str = "/app/certs/client.key"

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@aqims.local"

    # FOTA
    fota_server_url: str = "https://aqims.local/fota"
    fota_secret_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
