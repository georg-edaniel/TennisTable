#!/usr/bin/env python3
"""
AQIMS — Configuration InfluxDB
Configure le bucket, la politique de rétention (90 jours raw / 1 an agrégé)
et vérifie que l'écriture + la lecture fonctionnent.

Usage :
    python scripts/setup_influxdb.py --token <TOKEN>
    python scripts/setup_influxdb.py --host http://localhost:8086 --token <TOKEN>

Le TOKEN est celui défini dans .env : INFLUX_TOKEN=...
"""
import argparse
import sys
from datetime import datetime, timezone

# ── Vérification de la dépendance ────────────────────────────
try:
    from influxdb_client import InfluxDBClient, Point, BucketRetentionRules
    from influxdb_client.client.write_api import SYNCHRONOUS
except ImportError:
    print("❌  influxdb-client non installé.")
    print("    pip install influxdb-client==1.43.0")
    sys.exit(1)

# ── Constantes par défaut ─────────────────────────────────────
DEFAULT_HOST    = "http://localhost:8086"
DEFAULT_ORG     = "aqims"
DEFAULT_BUCKET  = "air_quality"
RETENTION_DAYS  = 90    # données brutes conservées 90 jours
DOWNSAMPLE_DAYS = 365   # agrégats 1 h conservés 1 an

FIELDS = ["temperature", "humidity", "co_ppm", "lux", "ldr_raw",
          "mq7_raw", "temp_ds", "aqi"]


def check_connection(client: InfluxDBClient, host: str) -> bool:
    try:
        h = client.health()
        print(f"✅  InfluxDB {h.version} — statut : {h.status}")
        return True
    except Exception as e:
        print(f"❌  Impossible de se connecter à {host}")
        print(f"    {e}")
        return False


def setup_bucket(client: InfluxDBClient, org: str, bucket: str) -> bool:
    api = client.buckets_api()
    existing = api.find_bucket_by_name(bucket)

    if existing:
        current_ret = existing.retention_rules
        print(f"✅  Bucket '{bucket}' existe déjà")
        if current_ret:
            days = current_ret[0].every_seconds // 86400
            print(f"    Rétention actuelle : {days} jours")
        return True

    retention = BucketRetentionRules(
        type="expire",
        every_seconds=RETENTION_DAYS * 86400,
    )
    api.create_bucket(bucket_name=bucket, retention_rules=retention, org=org)
    print(f"✅  Bucket '{bucket}' créé")
    print(f"    Rétention : {RETENTION_DAYS} jours (données brutes)")
    return True


def create_downsample_task(client: InfluxDBClient, org: str, bucket: str) -> None:
    """
    Crée une tâche Flux qui agrège les données par heure et les écrit
    dans un bucket '{bucket}_1h' (conservation 1 an).
    Ignorée si la tâche existe déjà.
    """
    tasks_api = client.tasks_api()
    task_name = f"aqims_downsample_{bucket}_1h"

    # Vérifier si la tâche existe déjà
    existing = tasks_api.find_tasks(name=task_name)
    if existing:
        print(f"✅  Tâche de downsampling '{task_name}' existe déjà")
        return

    # Créer le bucket de destination s'il n'existe pas
    dest_bucket = f"{bucket}_1h"
    api = client.buckets_api()
    if not api.find_bucket_by_name(dest_bucket):
        retention = BucketRetentionRules(
            type="expire",
            every_seconds=DOWNSAMPLE_DAYS * 86400,
        )
        api.create_bucket(bucket_name=dest_bucket, retention_rules=retention, org=org)
        print(f"✅  Bucket '{dest_bucket}' créé (rétention : {DOWNSAMPLE_DAYS} jours)")

    # Requête Flux de downsampling (moyenne toutes les heures)
    flux = f"""
option task = {{name: "{task_name}", every: 1h}}

from(bucket: "{bucket}")
  |> range(start: -task.lastSuccessTime)
  |> filter(fn: (r) => r["_measurement"] == "air_quality")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> to(bucket: "{dest_bucket}", org: "{org}")
"""
    tasks_api.create_task_every(
        name=task_name,
        flux=flux,
        every="1h",
        organization=org,
    )
    print(f"✅  Tâche de downsampling créée : '{task_name}'")
    print(f"    → données agrégées (1h) dans '{dest_bucket}' pendant {DOWNSAMPLE_DAYS} jours")


def test_write_read(client: InfluxDBClient, org: str, bucket: str) -> bool:
    write_api = client.write_api(write_options=SYNCHRONOUS)
    query_api  = client.query_api()

    # Écriture d'un point de test
    point = (
        Point("air_quality")
        .tag("device_id", "_setup_test")
        .tag("location",  "setup")
        .field("aqi",         0)
        .field("co_ppm",      0.0)
        .field("temperature", 20.0)
        .field("humidity",    50.0)
        .field("lux",         0.0)
        .field("ldr_raw",     0)
        .field("mq7_raw",     0)
        .field("temp_ds",     20.0)
        .time(datetime.now(timezone.utc))
    )
    try:
        write_api.write(bucket=bucket, org=org, record=point)
        print("✅  Test écriture OK")
    except Exception as e:
        print(f"❌  Échec écriture : {e}")
        return False

    # Lecture du point de test
    try:
        flux = f"""
from(bucket: "{bucket}")
  |> range(start: -1m)
  |> filter(fn: (r) => r["device_id"] == "_setup_test")
  |> limit(n: 1)
"""
        tables = query_api.query(flux, org=org)
        count = sum(len(t.records) for t in tables)
        print(f"✅  Test lecture OK ({count} point(s) retrouvé(s))")
    except Exception as e:
        print(f"❌  Échec lecture : {e}")
        return False

    return True


def print_summary(host: str, org: str, bucket: str) -> None:
    print()
    print("━" * 55)
    print("🎉  InfluxDB prêt pour AQIMS !")
    print("━" * 55)
    print(f"  UI admin   : {host}")
    print(f"  Org        : {org}")
    print(f"  Bucket raw : {bucket}  ({RETENTION_DAYS} jours)")
    print(f"  Bucket 1h  : {bucket}_1h  ({DOWNSAMPLE_DAYS} jours)")
    print()
    print("  Requête de test (Flux) :")
    print(f'  from(bucket: "{bucket}")')
    print(f'    |> range(start: -1h)')
    print(f'    |> filter(fn: (r) => r["_measurement"] == "air_quality")')
    print()
    print("  Champs disponibles :", ", ".join(FIELDS))
    print("━" * 55)


def main():
    parser = argparse.ArgumentParser(
        description="Configure InfluxDB pour AQIMS",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host",   default=DEFAULT_HOST,   help="URL InfluxDB")
    parser.add_argument("--token",  required=True,          help="Token API admin (INFLUX_TOKEN dans .env)")
    parser.add_argument("--org",    default=DEFAULT_ORG,    help="Organisation InfluxDB")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="Nom du bucket principal")
    parser.add_argument("--no-downsample", action="store_true",
                        help="Ne pas créer la tâche de downsampling")
    args = parser.parse_args()

    print("=" * 55)
    print("  AQIMS — Setup InfluxDB")
    print("=" * 55)
    print(f"  Host   : {args.host}")
    print(f"  Org    : {args.org}")
    print(f"  Bucket : {args.bucket}")
    print()

    client = InfluxDBClient(url=args.host, token=args.token, org=args.org)

    if not check_connection(client, args.host):
        sys.exit(1)

    if not setup_bucket(client, args.org, args.bucket):
        sys.exit(1)

    if not args.no_downsample:
        try:
            create_downsample_task(client, args.org, args.bucket)
        except Exception as e:
            print(f"⚠️   Tâche de downsampling ignorée : {e}")

    if not test_write_read(client, args.org, args.bucket):
        sys.exit(1)

    print_summary(args.host, args.org, args.bucket)

    client.__del__()


if __name__ == "__main__":
    main()
