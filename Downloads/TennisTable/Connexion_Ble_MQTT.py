"""
BLE MQTT TABLE TENNIS - VERSION 3.3
Améliorations vs v3.2 :
  - importlib.invalidate_caches() après pip install
  - Replay offline : filtrage des status/heartbeats périmés
  - sudo non-bloquant : pkexec en fallback (pas de prompt interactif)
  - Bluetooth macOS : system_profiler intégré + suggestion blueutil
  - Mosquitto Windows : fallback choco → scoop si winget absent
  - Tests unitaires : test_system.py (sans hardware)
Format JSON Node-RED inchangé (topic tabletennis/data).
"""

import importlib.util
import subprocess
import sys

# ======================================================
# AUTO-INSTALL bleak + paho-mqtt (avant tout import)
# Si absent → pip install automatique, puis import normal.
# Ignoré dans le bundle PyInstaller (tout est déjà embarqué).
# ======================================================

def _pip_install(spec: str) -> None:
    print(f"[INSTALL] '{spec}' absent — installation en cours…")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", spec, "--quiet"],
        check=False,
    )
    if r.returncode == 0:
        importlib.invalidate_caches()   # rafraîchit sys.path pour trouver le nouveau package
        print(f"[INSTALL] '{spec}' installé avec succès")
    else:
        print(f"[INSTALL] ERREUR : impossible d'installer '{spec}'")
        print(f"[INSTALL] → Exécutez manuellement : pip install {spec}")

if not getattr(sys, "frozen", False):          # pas dans un exe PyInstaller
    if importlib.util.find_spec("bleak") is None:
        _pip_install("bleak>=0.21.0")
    if importlib.util.find_spec("paho") is None:
        _pip_install("paho-mqtt>=1.6.0")

# ======================================================
# IMPORTS PRINCIPAUX
# ======================================================

import asyncio
import json
import logging
import logging.handlers
import os
import shutil
import socket
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from bleak import BleakClient, BleakScanner
import paho.mqtt.client as mqtt

# ======================================================
# CONSTANTES GLOBALES
# ======================================================

STROKE_NAMES: Dict[int, str] = {
    0: "BH Drive",
    1: "BH Smash",
    2: "FH Drive",
    3: "FH Loop",
    4: "FH Smash",
}

STROKE_KEYS: Dict[int, str] = {
    0: "bh_drive",
    1: "bh_smash",
    2: "fh_drive",
    3: "fh_loop",
    4: "fh_smash",
}

_DEFAULT_CONFIG: dict = {
    "mqtt": {
        "broker_host": "127.0.0.1",
        "broker_port": 1883,
        "client_id": "tabletennis_system",
        "keepalive": 60,
        "qos": 2,
        "topic_data": "tabletennis/data",
        "topic_startup": "tabletennis/system/startup",
        "topic_status": "tabletennis/system/status",
        "topic_reset": "tabletennis/system/reset",
        "reconnect_delay_min_s": 2,
        "reconnect_delay_max_s": 60,
        "reconnect_backoff_factor": 2,
        "offline_queue_size": 100,
    },
    "ble": {
        "stroke_char_uuid": "19B10001-E8F2-537E-4F6C-D104768A1214",
        "scan_timeout_s": 5,
        "connect_timeout_s": 15,
        "retry_delay_s": 3,
        "retry_delay_max_s": 60,
        "retry_backoff_factor": 2,
        "heartbeat_interval_s": 30,
    },
    "devices": [
        {"device_name": "TableTennisBat1", "player_name": "Joueur 1", "cooldown_ms": 800},
        {"device_name": "TableTennisBat2", "player_name": "Joueur 2", "cooldown_ms": 800},
    ],
    "logging": {
        "level": "INFO",
        "log_dir": "logs",
        "max_bytes": 1_048_576,
        "backup_count": 5,
        "console": True,
    },
    "stats": {
        "persist_file": "tabletennis_session.json",
        "persist_on_stroke": True,
    },
}


# ======================================================
# 1. ConfigLoader
# ======================================================

class ConfigLoader:
    """
    Cherche config.json :
      1. À côté du .exe (ou du script) — override opérateur
      2. Dans sys._MEIPASS (bundle PyInstaller)
      3. Valeurs par défaut hardcodées
    """

    def __init__(self) -> None:
        self._config: Optional[dict] = None

    def load_safe(self) -> dict:
        if self._config is not None:
            return self._config

        raw: Optional[dict] = None
        exe_dir = (
            Path(sys.executable).parent
            if getattr(sys, "frozen", False)
            else Path(__file__).parent
        )
        candidates = [exe_dir / "config.json"]
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "config.json")

        for candidate in candidates:
            if candidate.exists():
                try:
                    raw = json.loads(candidate.read_text(encoding="utf-8"))
                    break
                except Exception:
                    pass

        self._config = self._deep_merge(_DEFAULT_CONFIG, raw or {})
        return self._config

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        result = dict(base)
        for key, val in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = ConfigLoader._deep_merge(result[key], val)
            else:
                result[key] = val
        return result


# ======================================================
# 2. LoggerFactory
# ======================================================

class LoggerFactory:
    _initialized: bool = False

    @classmethod
    def setup(cls, log_cfg: dict) -> None:
        if cls._initialized:
            return
        cls._initialized = True

        level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
        root = logging.getLogger("tabletennis")
        root.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        base_dir = (
            Path(sys.executable).parent
            if getattr(sys, "frozen", False)
            else Path(__file__).parent
        )
        log_dir = base_dir / log_cfg.get("log_dir", "logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        fh = logging.handlers.RotatingFileHandler(
            log_dir / "tabletennis.log",
            maxBytes=log_cfg.get("max_bytes", 1_048_576),
            backupCount=log_cfg.get("backup_count", 5),
            encoding="utf-8",
        )
        fh.setFormatter(formatter)
        root.addHandler(fh)

        if log_cfg.get("console", True):
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(formatter)
            root.addHandler(ch)

    @staticmethod
    def get(name: str) -> logging.Logger:
        return logging.getLogger(f"tabletennis.{name}")


# ======================================================
# 3. StatsStore
# ======================================================

class StatsStore:
    _BLANK: dict = {
        k: 0
        for k in ("bh_drive", "bh_smash", "fh_drive", "fh_loop", "fh_smash", "total", "stroke_count")
    }

    def __init__(self, stats_cfg: dict) -> None:
        self._log = LoggerFactory.get("stats")
        base_dir = (
            Path(sys.executable).parent
            if getattr(sys, "frozen", False)
            else Path(__file__).parent
        )
        self._path = base_dir / stats_cfg.get("persist_file", "tabletennis_session.json")
        self._persist_on_stroke: bool = stats_cfg.get("persist_on_stroke", True)
        self._lock = threading.Lock()   # protège _data contre accès concurrent (thread paho ↔ asyncio)
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data = loaded
                    self._log.info("Stats rechargées depuis %s", self._path)
                    return
            except Exception as exc:
                self._log.warning("Impossible de lire %s : %s", self._path, exc)
        self._data = {}

    def get_device(self, device_name: str) -> dict:
        # Appelé sous lock — ne pas acquérir ici
        if device_name not in self._data:
            self._data[device_name] = dict(self._BLANK)
        return self._data[device_name]

    def increment(self, device_name: str, stroke_key: str) -> None:
        with self._lock:
            d = self.get_device(device_name)
            d[stroke_key] = d.get(stroke_key, 0) + 1
            d["total"] = d.get("total", 0) + 1
            d["stroke_count"] = d.get("stroke_count", 0) + 1
        if self._persist_on_stroke:
            self._save()

    def reset_all(self) -> None:
        with self._lock:
            self._data = {}
        self._save()
        self._log.info("Statistiques remises à zéro")

    def save(self) -> None:
        self._save()

    def _save(self) -> None:
        with self._lock:
            snapshot = json.dumps(self._data, indent=2, ensure_ascii=False)
        tmp = self._path.with_suffix(".tmp")
        try:
            tmp.write_text(snapshot, encoding="utf-8")
            tmp.replace(self._path)
        except Exception as exc:
            self._log.error("Échec sauvegarde stats : %s", exc)


# ======================================================
# 4. MqttManager — avec file d'attente offline
# ======================================================

class MqttManager:
    """
    MQTT avec :
      - Reconnexion auto (paho reconnect_delay_set + loop_start)
      - File d'attente offline (deque maxlen) → replay complet à la reconnexion
    """

    def __init__(self, mqtt_cfg: dict, on_reset_callback: Any, bridge=None) -> None:
        self._cfg = mqtt_cfg
        self._on_reset = on_reset_callback
        self._bridge = bridge
        self._log = LoggerFactory.get("mqtt")
        self._online: bool = False
        self._queue: deque = deque(maxlen=mqtt_cfg.get("offline_queue_size", 100))

        self._client = mqtt.Client(
            client_id=mqtt_cfg.get("client_id", "tabletennis_system"),
            clean_session=True,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(
            min_delay=mqtt_cfg.get("reconnect_delay_min_s", 2),
            max_delay=mqtt_cfg.get("reconnect_delay_max_s", 60),
        )

    # ---- callbacks paho ----

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        if rc != 0:
            self._log.warning("Échec connexion MQTT rc=%d", rc)
            return

        self._online = True
        self._log.info(
            "Connecté au broker MQTT (%s:%d)",
            self._cfg["broker_host"],
            self._cfg["broker_port"],
        )
        if self._bridge:
            self._bridge.mqtt_connected.emit(True)
        client.subscribe(self._cfg.get("topic_reset", "tabletennis/system/reset"), qos=1)

        # Replay de la file d'attente offline
        # Seuls les messages de données sont rejoués — status et heartbeats
        # périmés sont ignorés (ils ne reflètent plus l'état réel).
        if self._queue:
            topic_data = self._cfg.get("topic_data", "tabletennis/data")
            all_msgs = list(self._queue)
            self._queue.clear()
            to_replay = [(t, p, q) for t, p, q in all_msgs if t == topic_data]
            stale    = len(all_msgs) - len(to_replay)
            if stale:
                self._log.debug("%d message(s) status/heartbeat périmés ignorés", stale)
            if to_replay:
                self._log.info("Replay de %d message(s) de données…", len(to_replay))
                for topic, payload, qos in to_replay:
                    try:
                        client.publish(topic, payload, qos=qos)
                    except Exception as exc:
                        self._log.warning("Erreur replay MQTT : %s", exc)

    def _on_disconnect(self, client: Any, userdata: Any, rc: int) -> None:
        self._online = False
        if self._bridge:
            self._bridge.mqtt_connected.emit(False)
        if rc != 0:
            self._log.warning("Déconnexion MQTT inattendue (rc=%d) — reconnexion auto…", rc)
        else:
            self._log.info("Déconnexion MQTT propre")

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            if payload.get("action") == "reset":
                self._log.info("Commande reset reçue via MQTT")
                self._on_reset()
        except Exception as exc:
            self._log.warning("Message MQTT invalide : %s", exc)

    # ---- API publique ----

    def start(self) -> None:
        try:
            self._client.connect(
                self._cfg.get("broker_host", "127.0.0.1"),
                self._cfg.get("broker_port", 1883),
                self._cfg.get("keepalive", 60),
            )
            self._log.info("Tentative de connexion MQTT…")
        except Exception as exc:
            self._log.warning(
                "Connexion MQTT initiale échouée : %s — reconnexion auto activée", exc
            )
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        try:
            self._client.disconnect()
        except Exception:
            pass

    def is_connected(self) -> bool:
        return self._online

    def publish(self, topic: str, payload: str, qos: int = 2) -> None:
        if not self._online:
            self._queue.append((topic, payload, qos))
            self._log.debug(
                "MQTT hors ligne — message en attente (topic=%s, queue=%d/%d)",
                topic,
                len(self._queue),
                self._queue.maxlen,
            )
            return
        try:
            self._client.publish(topic, payload, qos=qos)
        except Exception as exc:
            self._log.warning("Échec publish MQTT : %s", exc)


# ======================================================
# 5. SharedBleScanner — un seul scan pour tous les devices
# ======================================================

class SharedBleScanner:
    """
    Lance un unique BleakScanner.discover() en boucle et distribue
    les résultats à chaque device via une asyncio.Queue dédiée.
    Résout les conflits WinRT/BlueZ causés par des scans simultanés.
    """

    def __init__(self, ble_cfg: dict, shutdown_event: asyncio.Event) -> None:
        self._timeout: float = ble_cfg.get("scan_timeout_s", 5)
        self._shutdown = shutdown_event
        self._queues: Dict[str, asyncio.Queue] = {}
        self._log = LoggerFactory.get("scanner")

    def register(self, device_name: str) -> asyncio.Queue:
        """Enregistre un device et retourne sa queue de résultats."""
        q: asyncio.Queue = asyncio.Queue(maxsize=1)
        self._queues[device_name] = q
        return q

    async def run(self) -> None:
        self._log.info("Scanner BLE partagé démarré (timeout=%ds/cycle)", self._timeout)
        while not self._shutdown.is_set():
            try:
                found = await BleakScanner.discover(timeout=self._timeout)
                self._log.debug("%d devices BLE détectés", len(found))

                for d in found:
                    if not d.name:
                        continue
                    for dev_name, queue in self._queues.items():
                        if dev_name.lower() in d.name.lower():
                            # Remplacer toute entrée périmée par la plus récente
                            while not queue.empty():
                                try:
                                    queue.get_nowait()
                                except asyncio.QueueEmpty:
                                    break
                            try:
                                queue.put_nowait(d)
                            except asyncio.QueueFull:
                                pass

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._log.warning("Erreur scan BLE : %s", exc)
                try:
                    await asyncio.wait_for(self._shutdown.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass

        self._log.info("Scanner BLE arrêté")


# ======================================================
# 6. TableTennisDevice
# ======================================================

class TableTennisDevice:
    """
    Gère un device BLE : attend le résultat du scanner partagé,
    se connecte, reçoit les coups, envoie un heartbeat.
    Backoff exponentiel sur les échecs de connexion.
    """

    def __init__(
        self,
        device_cfg: dict,
        ble_cfg: dict,
        mqtt_cfg: dict,
        mqtt_manager: MqttManager,
        stats_store: StatsStore,
        scan_queue: asyncio.Queue,
        shutdown_event: asyncio.Event,
        bridge=None,
    ) -> None:
        self._dcfg = device_cfg
        self._ble = ble_cfg
        self._mqcfg = mqtt_cfg
        self._mqtt = mqtt_manager
        self._stats = stats_store
        self._scan_queue = scan_queue
        self._shutdown = shutdown_event
        self._bridge = bridge

        self.device_name: str = device_cfg["device_name"]
        self.player_name: str = device_cfg.get("player_name", self.device_name)
        self._cooldown_s: float = device_cfg.get("cooldown_ms", 800) / 1000.0
        self._last_stroke_time: Optional[datetime] = None
        self._last_stroke_info: Optional[dict] = None

        self._log = LoggerFactory.get(self.device_name)
        self._log.info("Device initialisé — joueur : %s", self.player_name)

    # ---- Publication ----

    def _publish_data(self) -> None:
        s = self._stats.get_device(self.device_name)
        payload: dict = {
            "bh_drive": s.get("bh_drive", 0),
            "bh_smash": s.get("bh_smash", 0),
            "fh_drive": s.get("fh_drive", 0),
            "fh_loop": s.get("fh_loop", 0),
            "fh_smash": s.get("fh_smash", 0),
            "total": s.get("total", 0),
            "stroke_count": s.get("stroke_count", 0),
            "device": self.device_name,
            "timestamp": datetime.now().isoformat(),
        }
        if self._last_stroke_info:
            payload["last_stroke"] = self._last_stroke_info
        self._mqtt.publish(
            self._mqcfg.get("topic_data", "tabletennis/data"),
            json.dumps(payload, ensure_ascii=False),
            qos=self._mqcfg.get("qos", 2),
        )
        if self._bridge:
            self._bridge.stats_updated.emit(payload)
        self._log.debug("Publié — total=%d", payload["total"])

    def _publish_status(self, online: bool) -> None:
        self._mqtt.publish(
            self._mqcfg.get("topic_status", "tabletennis/system/status"),
            json.dumps(
                {
                    "device": self.device_name,
                    "online": online,
                    "timestamp": datetime.now().isoformat(),
                },
                ensure_ascii=False,
            ),
            qos=1,
        )
        if self._bridge:
            self._bridge.status_updated.emit(self.device_name, online)

    # ---- Gestion des coups BLE ----

    def _handle_stroke(self, sender: Any, data: bytearray) -> None:
        try:
            if len(data) != 1:
                return
            now = datetime.now()
            if (
                self._last_stroke_time
                and (now - self._last_stroke_time).total_seconds() < self._cooldown_s
            ):
                return
            self._last_stroke_time = now

            stroke_type = int(data[0])
            if stroke_type not in STROKE_NAMES:
                self._log.warning("Type de coup inconnu : %d", stroke_type)
                return

            stroke_key = STROKE_KEYS[stroke_type]
            self._stats.increment(self.device_name, stroke_key)

            self._last_stroke_info = {
                "id": self._stats.get_device(self.device_name)["stroke_count"],
                "type": stroke_type,
                "name": STROKE_NAMES[stroke_type],
                "time": now.strftime("%H:%M:%S.%f")[:-3],
                "timestamp": now.isoformat(),
            }
            self._publish_data()
            self._log.info(
                "%s — total=%d",
                STROKE_NAMES[stroke_type],
                self._stats.get_device(self.device_name)["total"],
            )
        except Exception as exc:
            self._log.error("Erreur traitement coup : %s", exc)

    # ---- Heartbeat ----

    async def _heartbeat_loop(self) -> None:
        interval: float = self._ble.get("heartbeat_interval_s", 30)
        while not self._shutdown.is_set():
            self._publish_status(online=True)
            self._log.debug("Heartbeat envoyé")
            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    # ---- Attente scanner (interruptible par shutdown) ----

    async def _wait_for_target(self) -> Optional[Any]:
        """Attend le prochain device BLE trouvé. Retourne None si shutdown."""
        while not self._shutdown.is_set():
            try:
                return await asyncio.wait_for(self._scan_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
        return None

    # ---- Boucle principale ----

    async def connect_and_run(self) -> None:
        self._log.info("Démarrage — attente du scanner BLE partagé")

        retry_delay: float = self._ble.get("retry_delay_s", 3)
        retry_max: float = self._ble.get("retry_delay_max_s", 60)
        backoff_factor: float = self._ble.get("retry_backoff_factor", 2)
        current_delay: float = retry_delay

        while not self._shutdown.is_set():
            # Vider les résultats périmés avant d'attendre un nouveau scan
            while not self._scan_queue.empty():
                try:
                    self._scan_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            self._log.info("En attente de détection BLE… (backoff actuel=%.0fs)", current_delay)
            target = await self._wait_for_target()
            if target is None:
                break  # shutdown demandé

            try:
                async with BleakClient(
                    target.address,
                    timeout=self._ble.get("connect_timeout_s", 15),
                ) as client:
                    self._log.info("Connecté (%s)", target.address)
                    current_delay = retry_delay  # reset backoff après succès
                    self._publish_status(online=True)
                    self._publish_data()

                    await client.start_notify(
                        self._ble.get(
                            "stroke_char_uuid", "19B10001-E8F2-537E-4F6C-D104768A1214"
                        ),
                        self._handle_stroke,
                    )
                    self._log.info("Prêt — en attente des coups")

                    hb_task = asyncio.create_task(self._heartbeat_loop())
                    try:
                        while client.is_connected and not self._shutdown.is_set():
                            await asyncio.sleep(1)
                    finally:
                        hb_task.cancel()
                        try:
                            await hb_task
                        except asyncio.CancelledError:
                            pass

                    self._log.info("Déconnecté (BLE)")
                    self._publish_status(online=False)
                    current_delay = retry_delay  # reset après déconnexion normale

            except asyncio.TimeoutError:
                self._log.warning("Timeout connexion BLE — retry dans %.0fs", current_delay)
                self._publish_status(online=False)
            except Exception as exc:
                self._log.warning("Erreur BLE : %s — retry dans %.0fs", exc, current_delay)
                self._publish_status(online=False)

            if not self._shutdown.is_set():
                try:
                    await asyncio.wait_for(self._shutdown.wait(), timeout=current_delay)
                except asyncio.TimeoutError:
                    pass
                # Augmenter le backoff pour le prochain échec
                current_delay = min(current_delay * backoff_factor, retry_max)

        self._log.info("Arrêté")


# ======================================================
# 7. TableTennisSystem
# ======================================================

class TableTennisSystem:
    VERSION = "3.3"

    def __init__(self, bridge=None) -> None:
        self._bridge = bridge
        cfg_loader = ConfigLoader()
        self._cfg = cfg_loader.load_safe()

        LoggerFactory.setup(self._cfg["logging"])
        self._log = LoggerFactory.get("system")
        self._log.info("TableTennis System v%s démarrage", self.VERSION)

        self._shutdown = asyncio.Event()
        self._stats = StatsStore(self._cfg["stats"])
        self._mqtt = MqttManager(
            self._cfg["mqtt"],
            on_reset_callback=self._on_reset,
            bridge=bridge,
        )

        self._scanner = SharedBleScanner(self._cfg["ble"], self._shutdown)
        self._devices: List[TableTennisDevice] = []
        for dcfg in self._cfg["devices"]:
            scan_queue = self._scanner.register(dcfg["device_name"])
            self._devices.append(
                TableTennisDevice(
                    device_cfg=dcfg,
                    ble_cfg=self._cfg["ble"],
                    mqtt_cfg=self._cfg["mqtt"],
                    mqtt_manager=self._mqtt,
                    stats_store=self._stats,
                    scan_queue=scan_queue,
                    shutdown_event=self._shutdown,
                    bridge=bridge,
                )
            )

    def _on_reset(self) -> None:
        self._stats.reset_all()
        for dev in self._devices:
            dev._last_stroke_info = None
        self._log.info("Reset complet des statistiques")
        if self._bridge:
            self._bridge.reset_done.emit()

    async def run(self) -> None:
        if self._bridge:
            self._bridge.set_loop(asyncio.get_event_loop(), self._on_reset)
        self._log.info("Démarrage MQTT…")
        self._mqtt.start()
        await asyncio.sleep(1)

        startup_msg = {
            "system": "TableTennis",
            "version": self.VERSION,
            "timestamp": datetime.now().isoformat(),
            "devices": [d.device_name for d in self._devices],
        }
        self._mqtt.publish(
            self._cfg["mqtt"].get("topic_startup", "tabletennis/system/startup"),
            json.dumps(startup_msg, ensure_ascii=False),
            qos=self._cfg["mqtt"].get("qos", 2),
        )

        self._log.info(
            "Système prêt — %d device(s) — broker %s:%d — topic %s",
            len(self._devices),
            self._cfg["mqtt"]["broker_host"],
            self._cfg["mqtt"]["broker_port"],
            self._cfg["mqtt"]["topic_data"],
        )

        scanner_task = asyncio.create_task(self._scanner.run())
        device_tasks = [asyncio.create_task(dev.connect_and_run()) for dev in self._devices]
        all_tasks = [scanner_task] + device_tasks

        try:
            await asyncio.gather(*all_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        finally:
            await self._graceful_shutdown(all_tasks)

    async def _graceful_shutdown(self, tasks: List[asyncio.Task]) -> None:
        self._log.info("Shutdown initié — attente max 5s…")
        self._shutdown.set()
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            self._log.warning("Timeout shutdown — annulation forcée")
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        self._stats.save()
        self._mqtt.stop()
        self._log.info("Arrêt complet — session sauvegardée")


# ======================================================
# EnvironmentChecker
# ======================================================

class EnvironmentChecker:
    """
    Vérifie et active automatiquement avant le démarrage :
      - Service Bluetooth (Windows / macOS / Linux)
      - Broker MQTT / Mosquitto (installation + démarrage)
    Ne lève jamais d'exception — loggue et continue en mode dégradé.
    """

    def __init__(self, mqtt_cfg: dict) -> None:
        self._host: str = mqtt_cfg.get("broker_host", "127.0.0.1")
        self._port: int = mqtt_cfg.get("broker_port", 1883)
        self._log = LoggerFactory.get("env")

    def run(self) -> None:
        self._log.info("=== Vérification de l'environnement système ===")
        self._ensure_python()
        self._ensure_packages()
        self._ensure_bluetooth()
        self._ensure_mqtt()
        self._log.info("=== Vérification terminée ===")

    # --------------------------------------------------
    # Python + packages
    # --------------------------------------------------

    def _ensure_python(self) -> None:
        """Vérifie la version Python. Fournit les instructions si trop ancienne."""
        major, minor = sys.version_info[:2]
        if (major, minor) >= (3, 9):
            self._log.info("✓ Python %d.%d", major, minor)
            return
        self._log.error(
            "✗ Python 3.9+ requis (actuel : %d.%d)\n"
            "  → Windows : winget install Python.Python.3\n"
            "              ou https://www.python.org/downloads/\n"
            "  → macOS   : brew install python3\n"
            "  → Linux   : sudo apt-get install python3 python3-pip",
            major, minor,
        )

    def _ensure_packages(self) -> None:
        """
        Vérifie bleak et paho-mqtt.
        Dans le bundle PyInstaller ils sont déjà embarqués → skip.
        En mode script, tente pip install si absent.
        """
        if getattr(sys, "frozen", False):
            self._log.info("✓ Packages Python embarqués (exe PyInstaller)")
            return

        packages = [
            ("bleak",     "bleak>=0.21.0"),
            ("paho",      "paho-mqtt>=1.6.0"),
        ]
        for import_name, pip_spec in packages:
            if importlib.util.find_spec(import_name) is not None:
                self._log.info("✓ Package '%s' disponible", import_name)
            else:
                self._log.warning("✗ Package '%s' manquant — installation…", import_name)
                r = subprocess.run(
                    [sys.executable, "-m", "pip", "install", pip_spec, "--quiet"],
                    check=False,
                )
                if r.returncode == 0:
                    self._log.info("✓ '%s' installé", import_name)
                else:
                    self._log.error(
                        "Impossible d'installer '%s'\n"
                        "  → pip install %s",
                        import_name, pip_spec,
                    )

    # --------------------------------------------------
    # MQTT
    # --------------------------------------------------

    def _is_mqtt_reachable(self) -> bool:
        try:
            with socket.create_connection((self._host, self._port), timeout=2):
                return True
        except OSError:
            return False

    def _ensure_mqtt(self) -> None:
        if self._is_mqtt_reachable():
            self._log.info("✓ Broker MQTT accessible (%s:%d)", self._host, self._port)
            return

        self._log.warning(
            "✗ Broker MQTT inaccessible — tentative de démarrage de Mosquitto…"
        )

        if sys.platform == "win32":
            self._mqtt_win()
        elif sys.platform == "darwin":
            self._mqtt_mac()
        else:
            self._mqtt_linux()

        time.sleep(2)
        if self._is_mqtt_reachable():
            self._log.info("✓ Broker MQTT démarré avec succès")
        else:
            self._log.warning(
                "✗ Broker MQTT toujours inaccessible — "
                "démarrage en mode offline (file d'attente active)"
            )

    def _mqtt_win(self) -> None:
        r = subprocess.run(
            ["sc", "query", "mosquitto"], capture_output=True, text=True
        )
        if "mosquitto" in r.stdout.lower():
            # Service présent → démarrer (avec élévation si nécessaire)
            r2 = subprocess.run(
                ["net", "start", "mosquitto"], capture_output=True, text=True
            )
            if r2.returncode != 0:
                self._log.info("Droits admin requis — élévation UAC…")
                self._elevate_win("net start mosquitto")
            return

        # Non installé → essayer les gestionnaires disponibles dans l'ordre
        self._log.info("Mosquitto non trouvé — recherche d'un gestionnaire de paquets…")
        pkg_cmds = [
            ("winget", [
                "winget", "install", "-e",
                "--id", "EclipseMosquitto.Mosquitto",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]),
            ("choco", ["choco", "install", "mosquitto", "-y", "--no-progress"]),
            ("scoop", ["scoop", "install", "mosquitto"]),
        ]
        for name, cmd in pkg_cmds:
            if shutil.which(cmd[0]):
                self._log.info("Tentative d'installation via %s…", name)
                try:
                    r2 = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=180
                    )
                    if r2.returncode == 0:
                        self._log.info("✓ Mosquitto installé via %s — démarrage…", name)
                        subprocess.run(["net", "start", "mosquitto"], capture_output=True)
                        return
                except subprocess.TimeoutExpired:
                    self._log.warning("Timeout installation via %s", name)

        self._log.error(
            "Aucun gestionnaire de paquets disponible (winget / choco / scoop).\n"
            "  → https://mosquitto.org/download/\n"
            "  → Le système démarre en mode offline."
        )

    def _mqtt_mac(self) -> None:
        if shutil.which("brew"):
            r = subprocess.run(["brew", "list", "mosquitto"], capture_output=True)
            if r.returncode != 0:
                self._log.info("Installation de Mosquitto via Homebrew…")
                subprocess.run(["brew", "install", "mosquitto"], timeout=300)
            subprocess.run(["brew", "services", "start", "mosquitto"])
        elif shutil.which("mosquitto"):
            # Installé sans brew → lancer en daemon
            subprocess.Popen(
                ["mosquitto", "-d"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            self._log.error(
                "Mosquitto non trouvé.\n"
                "  → Installez Homebrew : https://brew.sh\n"
                "  → Puis : brew install mosquitto && brew services start mosquitto"
            )

    def _mqtt_linux(self) -> None:
        if not shutil.which("mosquitto"):
            self._log.info("Installation de Mosquitto…")
            installed = False
            for pkg_mgr, cmd in [
                ("apt-get", ["apt-get", "install", "-y", "mosquitto"]),
                ("dnf",     ["dnf",     "install", "-y", "mosquitto"]),
                ("pacman",  ["pacman",  "-S", "--noconfirm", "mosquitto"]),
                ("snap",    ["snap",    "install", "mosquitto"]),
            ]:
                if shutil.which(pkg_mgr):
                    installed = self._sudo(cmd)
                    break
            if not installed:
                self._log.error(
                    "Gestionnaire de paquets non reconnu.\n"
                    "  → Installez manuellement : https://mosquitto.org/download/"
                )
                return

        self._sudo(["systemctl", "start",  "mosquitto"])
        self._sudo(["systemctl", "enable", "mosquitto"])

    # --------------------------------------------------
    # Bluetooth
    # --------------------------------------------------

    def _ensure_bluetooth(self) -> None:
        if sys.platform == "win32":
            self._bt_win()
        elif sys.platform == "darwin":
            self._bt_mac()
        else:
            self._bt_linux()

    def _bt_win(self) -> None:
        r = subprocess.run(["sc", "query", "bthserv"], capture_output=True, text=True)
        if "RUNNING" in r.stdout:
            self._log.info("✓ Service Bluetooth actif")
            return
        self._log.warning("Service Bluetooth arrêté — démarrage…")
        r2 = subprocess.run(["net", "start", "bthserv"], capture_output=True, text=True)
        if r2.returncode == 0:
            self._log.info("✓ Service Bluetooth démarré")
        else:
            self._log.info("Droits admin requis pour démarrer le Bluetooth…")
            self._elevate_win("net start bthserv")

    def _bt_mac(self) -> None:
        # Cas 1 : blueutil disponible (contrôle complet)
        if shutil.which("blueutil"):
            r = subprocess.run(["blueutil", "--power"], capture_output=True, text=True)
            if r.stdout.strip() == "0":
                self._log.warning("Bluetooth désactivé — activation via blueutil…")
                subprocess.run(["blueutil", "--power", "1"])
                time.sleep(1)
                self._log.info("✓ Bluetooth activé")
            else:
                self._log.info("✓ Bluetooth actif")
            return

        # Cas 2 : system_profiler (intégré macOS) — lecture seule, pas d'activation
        # Le format JSON varie selon la version macOS (10.15 → 14 Sonoma).
        # On teste plusieurs stratégies de parsing pour couvrir tous les cas.
        bt_on = False
        try:
            r = subprocess.run(
                ["system_profiler", "SPBluetoothDataType", "-json"],
                capture_output=True, text=True, timeout=10,
            )
            data = json.loads(r.stdout)
            bt_info = data.get("SPBluetoothDataType", [{}])[0]

            # Stratégie 1 : champ direct (macOS 10.15–12)
            for key in ("controller_state", "state", "apple_bluetooth_power"):
                val = str(bt_info.get(key, "")).lower()
                if val in ("on", "attivato", "activé", "enabled", "yes"):
                    bt_on = True
                    break

            # Stratégie 2 : chercher "On" récursivement dans tout le dict (macOS 13+)
            if not bt_on:
                raw_text = json.dumps(bt_info).lower()
                bt_on = ('"on"' in raw_text or '"enabled"' in raw_text
                         or '"attivato"' in raw_text)
        except Exception:
            pass

        # Stratégie 3 : fallback texte brut (si -json non supporté)
        if not bt_on:
            try:
                r2 = subprocess.run(
                    ["system_profiler", "SPBluetoothDataType"],
                    capture_output=True, text=True, timeout=10,
                )
                bt_on = "bluetooth power: on" in r2.stdout.lower()
            except Exception:
                pass

        if bt_on:
            self._log.info("✓ Bluetooth actif (system_profiler)")
            return

        # Cas 3 : impossible de vérifier/activer → guider l'utilisateur
        self._log.warning(
            "Impossible de vérifier ou d'activer le Bluetooth automatiquement.\n"
            "  → Activez-le dans Préférences Système → Bluetooth\n"
            "  → Pour le contrôle automatique : brew install blueutil"
        )

    def _bt_linux(self) -> None:
        r = subprocess.run(
            ["systemctl", "is-active", "bluetooth"],
            capture_output=True, text=True,
        )
        if "active" in r.stdout:
            self._log.info("✓ Service Bluetooth actif")
        else:
            self._log.warning("Service Bluetooth inactif — démarrage…")
            ok = self._sudo(["systemctl", "start", "bluetooth"])
            if ok:
                self._log.info("✓ Service Bluetooth démarré")
            else:
                self._log.error(
                    "Impossible de démarrer le service Bluetooth.\n"
                    "  → Exécutez : sudo systemctl start bluetooth"
                )
                return

        # Vérifier que l'utilisateur est dans le groupe bluetooth
        try:
            import grp, os
            user = os.environ.get("USER") or os.environ.get("USERNAME", "")
            bt_members = grp.getgrnam("bluetooth").gr_mem
            if user and user not in bt_members:
                self._log.warning(
                    "L'utilisateur '%s' n'est pas dans le groupe 'bluetooth'.\n"
                    "  → Exécutez : sudo usermod -aG bluetooth %s\n"
                    "  → Puis reconnectez-vous",
                    user, user,
                )
        except (KeyError, Exception):
            pass

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _sudo(self, cmd: List[str]) -> bool:
        """
        Lance une commande avec élévation, sans jamais bloquer sur un prompt.
        1. sudo -n   (passwordless / NOPASSWD)
        2. pkexec    (PolicyKit GUI — session graphique Linux)
        3. Échec propre + instructions claires
        """
        # 1. sudo non-interactif
        try:
            r = subprocess.run(
                ["sudo", "-n"] + cmd,
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                return True
        except Exception:
            pass

        # 2. pkexec — seulement si une session graphique est détectée
        # (sur serveur/SSH sans display, pkexec bloquerait indéfiniment)
        has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        if has_display and shutil.which("pkexec"):
            try:
                r = subprocess.run(
                    ["pkexec"] + cmd,
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode == 0:
                    return True
            except Exception:
                pass

        # 3. Droits insuffisants → instructions sans bloquer
        self._log.warning(
            "Droits insuffisants — exécutez manuellement :\n  sudo %s",
            " ".join(cmd),
        )
        return False

    def _elevate_win(self, cmd: str) -> None:
        """
        Relance une commande Windows avec élévation UAC.
        Attend jusqu'à 15s que la commande prenne effet (retry sur socket).
        """
        try:
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", "cmd.exe", f"/c {cmd}", None, 1
            )
        except Exception as exc:
            self._log.warning("Élévation Windows échouée : %s", exc)
            return
        # Attendre dynamiquement que le service soit opérationnel (max 15s)
        for _ in range(15):
            time.sleep(1)
            if self._is_mqtt_reachable():
                return


# ======================================================
# MAIN
# ======================================================

async def main() -> None:
    system = TableTennisSystem()
    try:
        await system.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    # Charger config + logger, puis vérifier/activer l'environnement
    _startup_cfg = ConfigLoader().load_safe()
    LoggerFactory.setup(_startup_cfg["logging"])
    EnvironmentChecker(_startup_cfg["mqtt"]).run()

    # Lancer l'interface PyQt6 si disponible, sinon mode console
    if importlib.util.find_spec("PyQt6") is not None:
        from gui import run_gui
        run_gui()
    else:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass
