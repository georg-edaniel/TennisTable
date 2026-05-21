#!/usr/bin/env python3
"""
Migration : devices.floor  TEXT → INTEGER
Exécuter depuis la racine du projet :
    python scripts/migrate_floor_to_int.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "aqims_dev.db"


def migrate() -> None:
    if not DB_PATH.exists():
        print(f"Base introuvable : {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Vérifier le type actuel
    cur.execute("PRAGMA table_info(devices)")
    cols = {row[1]: row[2] for row in cur.fetchall()}
    if "floor" not in cols:
        print("Colonne 'floor' introuvable — rien à faire.")
        conn.close()
        return
    if cols["floor"].upper() == "INTEGER":
        print("Colonne 'floor' déjà INTEGER — rien à faire.")
        conn.close()
        return

    print(f"Migration de devices.floor ({cols['floor']} → INTEGER)…")

    cur.executescript("""
        BEGIN;

        CREATE TABLE devices_new (
            id            INTEGER PRIMARY KEY,
            device_id     VARCHAR(64) UNIQUE NOT NULL,
            name          VARCHAR(100) NOT NULL,
            location      VARCHAR(200),
            description   TEXT,
            building      VARCHAR(100),
            floor         INTEGER,
            room          VARCHAR(100),
            lat           FLOAT,
            lng           FLOAT,
            firmware_version  VARCHAR(20),
            is_online     BOOLEAN,
            is_active     BOOLEAN,
            last_aqi      INTEGER,
            last_co_ppm   FLOAT,
            last_temperature FLOAT,
            last_humidity FLOAT,
            last_lux      FLOAT,
            alert_pm25_threshold FLOAT,
            alert_co2_threshold  FLOAT,
            alert_co_threshold   FLOAT,
            alert_aqi_threshold  INTEGER,
            alert_temp_max       FLOAT,
            alert_humidity_max   FLOAT,
            owner_id      INTEGER REFERENCES users(id),
            created_at    DATETIME,
            last_seen     DATETIME
        );

        INSERT INTO devices_new
        SELECT
            id, device_id, name, location, description, building,
            CASE
                WHEN floor GLOB '[0-9]*' THEN CAST(floor AS INTEGER)
                ELSE NULL
            END,
            room, lat, lng, firmware_version, is_online, is_active,
            last_aqi, last_co_ppm, last_temperature, last_humidity, last_lux,
            alert_pm25_threshold, alert_co2_threshold, alert_co_threshold,
            alert_aqi_threshold, alert_temp_max, alert_humidity_max,
            owner_id, created_at, last_seen
        FROM devices;

        DROP TABLE devices;
        ALTER TABLE devices_new RENAME TO devices;

        COMMIT;
    """)

    conn.close()
    print("Migration terminée.")


if __name__ == "__main__":
    migrate()
