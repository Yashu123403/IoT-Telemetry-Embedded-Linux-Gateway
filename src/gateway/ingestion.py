"""
Ingestion: subscribes to the telemetry and heartbeat topic wildcards on
the MQTT broker, validates each payload against the pydantic schemas
(defending against malformed/corrupt field data, exactly as a real
gateway must), and pushes valid messages onto the bounded TelemetryBuffer
for the processing loop to consume. Runs entirely on the MQTT client's
own network thread; deliberately does no heavy processing here so the
network thread is never blocked.
"""

from __future__ import annotations

from pydantic import ValidationError

from src.gateway.buffer import TelemetryBuffer
from src.protocols.mqtt_client_wrapper import MqttClientWrapper
from src.protocols.schemas import HeartbeatMessage, TelemetryMessage
from src.protocols.topics import HEARTBEAT_WILDCARD, TELEMETRY_WILDCARD
from src.utils.logger import get_logger

logger = get_logger(__name__)


class IngestionService:
    def __init__(
        self,
        mqtt_host: str,
        mqtt_port: int,
        telemetry_buffer: TelemetryBuffer,
        heartbeat_buffer: TelemetryBuffer,
        client_id: str = "gateway-ingestion",
    ) -> None:
        self._client = MqttClientWrapper(client_id=client_id, host=mqtt_host, port=mqtt_port)
        self._telemetry_buffer = telemetry_buffer
        self._heartbeat_buffer = heartbeat_buffer
        self._rejected_count = 0

    def start(self) -> None:
        self._client.connect()
        self._client.subscribe(TELEMETRY_WILDCARD, self._on_telemetry)
        self._client.subscribe(HEARTBEAT_WILDCARD, self._on_heartbeat)
        logger.info("Ingestion subscribed to %s and %s", TELEMETRY_WILDCARD, HEARTBEAT_WILDCARD)

    def stop(self) -> None:
        self._client.disconnect()

    def _on_telemetry(self, topic: str, payload: dict) -> None:
        try:
            msg = TelemetryMessage.model_validate(payload)
        except ValidationError as exc:
            self._rejected_count += 1
            logger.warning("Rejected malformed telemetry on %s: %s", topic, exc.errors()[:1])
            return
        accepted = self._telemetry_buffer.push(msg)
        if not accepted:
            logger.debug("Telemetry buffer full; dropped message from %s", msg.device_id)

    def _on_heartbeat(self, topic: str, payload: dict) -> None:
        try:
            msg = HeartbeatMessage.model_validate(payload)
        except ValidationError as exc:
            self._rejected_count += 1
            logger.warning("Rejected malformed heartbeat on %s: %s", topic, exc.errors()[:1])
            return
        self._heartbeat_buffer.push(msg)

    @property
    def rejected_count(self) -> int:
        return self._rejected_count

    def publish_command(self, device_id: str, command_payload: dict) -> None:
        from src.protocols.topics import command_topic
        self._client.publish(command_topic(device_id), command_payload)
