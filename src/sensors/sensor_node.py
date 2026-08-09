"""
SensorNode simulates one embedded field device: it owns a sensor
(temperature/humidity/vibration/current/gps), publishes telemetry on its
own interval, publishes periodic heartbeats (device-management liveness),
and listens for command messages from the gateway (e.g. change publish
interval) -- mirroring how a real Modbus/MQTT field node on an Industrial
IoT Gateway deployment behaves.

Runs each node in its own thread so a "fleet" of N simulated devices can
run concurrently in a single Python process on a laptop.
"""

from __future__ import annotations

import random
import threading
import time
from typing import Optional

from src.protocols.mqtt_client_wrapper import MqttClientWrapper
from src.protocols.schemas import DeviceCommand, HeartbeatMessage, TelemetryMessage
from src.protocols.topics import command_topic, heartbeat_topic, telemetry_topic
from src.sensors.gps_sensor import GpsSensor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SensorNode:
    def __init__(
        self,
        device_id: str,
        site: str,
        sensor,  # BaseSensor or GpsSensor
        publish_interval_sec: float,
        firmware_version: str,
        mqtt_host: str = "127.0.0.1",
        mqtt_port: int = 1883,
    ) -> None:
        self.device_id = device_id
        self._site = site
        self._sensor = sensor
        self._publish_interval_sec = publish_interval_sec
        self._firmware_version = firmware_version
        self._battery_pct = 100.0
        self._sequence = 0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._client = MqttClientWrapper(client_id=f"sensor-{device_id}", host=mqtt_host, port=mqtt_port)
        self._is_gps = isinstance(sensor, GpsSensor)

    def start(self) -> None:
        self._client.connect()
        self._client.subscribe(command_topic(self.device_id), self._on_command)
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name=f"sensor-{self.device_id}")
        self._thread.start()
        logger.info("SensorNode %s started (metric=%s, interval=%.1fs)",
                    self.device_id, self._sensor.metric_type, self._publish_interval_sec)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._client.disconnect()

    def _on_command(self, topic: str, payload: dict) -> None:
        try:
            cmd = DeviceCommand.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: rejected malformed command: %s", self.device_id, exc)
            return

        if cmd.command == "set_interval":
            new_interval = cmd.payload.get("interval_sec")
            if new_interval and new_interval > 0:
                logger.info("%s: interval changed %.1fs -> %.1fs (remote command)",
                            self.device_id, self._publish_interval_sec, new_interval)
                self._publish_interval_sec = float(new_interval)
        elif cmd.command == "reboot":
            logger.info("%s: simulated reboot (sequence counter reset)", self.device_id)
            self._sequence = 0
        else:
            logger.warning("%s: unknown command '%s'", self.device_id, cmd.command)

    def _run_loop(self) -> None:
        last_heartbeat = 0.0
        heartbeat_interval = max(self._publish_interval_sec * 3, 5.0)

        while not self._stop_event.is_set():
            self._publish_telemetry()
            now = time.monotonic()
            if now - last_heartbeat >= heartbeat_interval:
                self._publish_heartbeat()
                last_heartbeat = now
            self._stop_event.wait(self._publish_interval_sec)

    def _publish_telemetry(self) -> None:
        reading = self._sensor.read()
        if reading is None:
            return  # dropout fault: real device would simply not transmit

        self._sequence += 1
        self._battery_pct = max(0.0, self._battery_pct - random.uniform(0.0, 0.01))

        if self._is_gps:
            msg = TelemetryMessage(
                device_id=self.device_id,
                metric_type="gps",
                site=self._site,
                lat=reading.lat,
                lon=reading.lon,
                unit="deg",
                firmware_version=self._firmware_version,
                sequence=self._sequence,
                fault_flag=reading.fault_flag,
            )
        else:
            msg = TelemetryMessage(
                device_id=self.device_id,
                metric_type=self._sensor.metric_type,
                site=self._site,
                value=reading.value,
                unit=reading.unit,
                firmware_version=self._firmware_version,
                sequence=self._sequence,
                fault_flag=reading.fault_flag,
            )

        topic = telemetry_topic(self.device_id, msg.metric_type)
        self._client.publish(topic, msg.model_dump())

    def _publish_heartbeat(self) -> None:
        hb = HeartbeatMessage(
            device_id=self.device_id,
            site=self._site,
            firmware_version=self._firmware_version,
            battery_pct=round(self._battery_pct, 1),
        )
        self._client.publish(heartbeat_topic(self.device_id), hb.model_dump())
