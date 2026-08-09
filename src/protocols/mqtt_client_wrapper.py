"""
Thin wrapper around `paho-mqtt` giving publishers and subscribers a
consistent, minimal interface (connect-with-retry, JSON publish, callback
subscribe). Both the simulated sensor nodes and the gateway's ingestion
module use this instead of touching paho directly, so the rest of the
codebase isn't coupled to the MQTT client library's API.

Supports multiple independent subscriptions per client: each call to
subscribe() registers its own callback, matched against incoming message
topics using MQTT wildcard semantics (+ = single level, # = multi-level).
"""

from __future__ import annotations

import json
import time
from typing import Callable, List, Tuple

import paho.mqtt.client as mqtt

from src.utils.logger import get_logger

logger = get_logger(__name__)


def _topic_matches(topic_filter: str, topic: str) -> bool:
    """Minimal MQTT topic-filter matcher supporting '+' and trailing '#'."""
    filter_parts = topic_filter.split("/")
    topic_parts = topic.split("/")

    for i, fpart in enumerate(filter_parts):
        if fpart == "#":
            return True
        if i >= len(topic_parts):
            return False
        if fpart != "+" and fpart != topic_parts[i]:
            return False
    return len(filter_parts) == len(topic_parts)


class MqttClientWrapper:
    def __init__(self, client_id: str, host: str = "127.0.0.1", port: int = 1883, keepalive: int = 30) -> None:
        self._host = host
        self._port = port
        self._keepalive = keepalive
        self._client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self._subscriptions: List[Tuple[str, Callable[[str, dict], None]]] = []
        self._client.on_message = self._handle_message
        self._connected = False

    def connect(self, retries: int = 10, retry_delay_sec: float = 0.5) -> None:
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                self._client.connect(self._host, self._port, self._keepalive)
                self._client.loop_start()
                self._connected = True
                logger.info("Connected to MQTT broker %s:%d", self._host, self._port)
                return
            except (ConnectionRefusedError, OSError) as exc:
                last_exc = exc
                logger.warning("MQTT connect attempt %d/%d failed: %s", attempt, retries, exc)
                time.sleep(retry_delay_sec)
        raise ConnectionError(f"Could not connect to MQTT broker at {self._host}:{self._port}") from last_exc

    def disconnect(self) -> None:
        if self._connected:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False

    def publish(self, topic: str, payload: dict, qos: int = 0) -> None:
        self._client.publish(topic, json.dumps(payload), qos=qos)

    def subscribe(self, topic_filter: str, on_message: Callable[[str, dict], None], qos: int = 0) -> None:
        self._subscriptions.append((topic_filter, on_message))
        self._client.subscribe(topic_filter, qos=qos)

    def _handle_message(self, client, userdata, msg) -> None:  # noqa: ANN001
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Dropping malformed MQTT payload on topic %s", msg.topic)
            return

        matched = False
        for topic_filter, callback in self._subscriptions:
            if _topic_matches(topic_filter, msg.topic):
                matched = True
                callback(msg.topic, payload)
        if not matched:
            logger.debug("No subscription matched incoming topic %s", msg.topic)

    @property
    def is_connected(self) -> bool:
        return self._connected

