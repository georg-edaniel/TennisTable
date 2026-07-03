"""MQTT → asyncio bridge.

Runs paho in a background thread; passes payloads thread-safely into
an asyncio.Queue consumed by drain_loop().
"""
import asyncio
import json
import logging
import threading
from typing import Callable

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from .config import MqttConfig

logger = logging.getLogger("mqtt_bridge")


class MqttBridge:
    def __init__(self, cfg: MqttConfig, loop: asyncio.AbstractEventLoop):
        self._cfg = cfg
        self._loop = loop
        self._queue: asyncio.Queue = asyncio.Queue()
        self._client = mqtt.Client(CallbackAPIVersion.VERSION1, client_id=cfg.client_id + "_web")
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect
        self._connected = False
        self._thread: threading.Thread | None = None

    # ── paho callbacks (called from paho thread) ─────────────────────────────

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            client.subscribe(self._cfg.topic_data, qos=self._cfg.qos)
            client.subscribe(self._cfg.topic_status, qos=0)
            logger.info("MQTT bridge connected and subscribed.")
        else:
            logger.warning("MQTT bridge connect failed rc=%s", rc)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        logger.warning("MQTT bridge disconnected rc=%s — will auto-reconnect", rc)

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode())
            payload["_topic"] = message.topic
        except Exception:
            return
        # Thread-safe hand-off to asyncio loop
        self._loop.call_soon_threadsafe(self._queue.put_nowait, payload)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        self._client.connect_async(
            self._cfg.broker_host, self._cfg.broker_port, self._cfg.keepalive
        )
        self._thread = threading.Thread(
            target=self._client.loop_forever, daemon=True, name="mqtt_bridge"
        )
        self._thread.start()
        logger.info(
            "MQTT bridge thread started → %s:%s",
            self._cfg.broker_host,
            self._cfg.broker_port,
        )

    def stop(self):
        self._client.disconnect()
        if self._thread:
            self._thread.join(timeout=3)

    @property
    def connected(self) -> bool:
        return self._connected

    # ── Drain loop (runs in asyncio event loop) ───────────────────────────────

    async def drain_loop(self, ws_manager, record_callback: Callable):
        """Consume queue; broadcast live WS + persist via record_callback."""
        while True:
            try:
                payload = await self._queue.get()
                topic = payload.pop("_topic", "")

                if topic == self._cfg.topic_data:
                    # 1. Broadcast to all WS clients
                    await ws_manager.broadcast_all(
                        {"type": "stroke", "data": payload}
                    )
                    # 2. Persist if a session is active for this device
                    try:
                        await record_callback(payload)
                    except Exception as exc:
                        logger.debug("record_callback error: %s", exc)

                elif topic == self._cfg.topic_status:
                    await ws_manager.broadcast_all(
                        {"type": "status", "data": payload}
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("drain_loop error: %s", exc)
