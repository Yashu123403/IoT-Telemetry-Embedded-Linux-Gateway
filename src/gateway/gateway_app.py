"""
GatewayApp is the "embedded Linux gateway process": a long-running loop
that drains the ingestion buffer, applies the rule engine, updates the
windowed aggregator, records device management state, persists to
SQLite, and periodically sweeps for offline devices and purges expired
storage rows. This mirrors the responsibilities of a real Industrial IoT
Gateway service (see Mistral's Modular Industrial Gateway case study:
"gather or deliver data ... with a Web based GUI for Configuration and
Monitoring") running as a systemd-managed process on embedded Linux.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

import yaml

from src.gateway.aggregator import WindowedAggregator
from src.gateway.buffer import TelemetryBuffer
from src.gateway.device_registry import DeviceRegistry
from src.gateway.ingestion import IngestionService
from src.gateway.rule_engine import RuleEngine
from src.gateway.storage import AlertRow, TelemetryRow, TelemetryStore
from src.gateway.system_monitor import SystemMonitor
from src.protocols.schemas import HeartbeatMessage, TelemetryMessage
from src.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "gateway.yaml"


def load_gateway_config(config_path: Optional[str] = None) -> dict:
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["gateway"]


class GatewayApp:
    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config = load_gateway_config(config_path)
        limits = self.config["resource_limits"]

        self.telemetry_buffer = TelemetryBuffer(
            max_messages=limits["buffer_max_messages"],
            overflow_policy=limits["buffer_overflow_policy"],
        )
        self.heartbeat_buffer = TelemetryBuffer(
            max_messages=limits["buffer_max_messages"],
            overflow_policy=limits["buffer_overflow_policy"],
        )
        self.registry = DeviceRegistry(
            heartbeat_timeout_sec=self.config["device_management"]["heartbeat_timeout_sec"]
        )
        self.aggregator = WindowedAggregator(window_sec=self.config["aggregation"]["window_sec"])
        self.rule_engine = RuleEngine(self.config["rules"])
        self.store = TelemetryStore(
            db_path=self.config["storage"]["sqlite_path"],
            retention_hours=self.config["storage"]["retention_hours"],
        )
        self.system_monitor = SystemMonitor(ram_ceiling_mb=limits["ram_ceiling_mb"])

        broker_cfg = self.config["mqtt_broker"]
        self.ingestion = IngestionService(
            mqtt_host=broker_cfg["host"],
            mqtt_port=broker_cfg["port"],
            telemetry_buffer=self.telemetry_buffer,
            heartbeat_buffer=self.heartbeat_buffer,
        )

        self._stop_event = threading.Event()
        self._processing_thread: Optional[threading.Thread] = None
        self._maintenance_thread: Optional[threading.Thread] = None
        self.recent_alerts: list = []
        self._alerts_lock = threading.Lock()
        self.stats = {
            "processed_telemetry": 0,
            "processed_heartbeats": 0,
            "alerts_raised": 0,
            "started_at": time.time(),
        }

    def start(self) -> None:
        self.ingestion.start()
        self._processing_thread = threading.Thread(target=self._processing_loop, daemon=True, name="gateway-processing")
        self._maintenance_thread = threading.Thread(target=self._maintenance_loop, daemon=True, name="gateway-maintenance")
        self._processing_thread.start()
        self._maintenance_thread.start()
        logger.info("GatewayApp '%s' started", self.config["gateway_id"])

    def stop(self) -> None:
        self._stop_event.set()
        if self._processing_thread:
            self._processing_thread.join(timeout=2.0)
        if self._maintenance_thread:
            self._maintenance_thread.join(timeout=2.0)
        self.ingestion.stop()
        self.store.close()
        logger.info("GatewayApp stopped")

    def _processing_loop(self) -> None:
        while not self._stop_event.is_set():
            self._drain_telemetry()
            self._drain_heartbeats()
            time.sleep(0.05)

    def _drain_telemetry(self) -> None:
        messages = self.telemetry_buffer.drain(max_items=50)
        for msg in messages:
            self._process_telemetry(msg)

    def _drain_heartbeats(self) -> None:
        messages = self.heartbeat_buffer.drain(max_items=50)
        for msg in messages:
            self._process_heartbeat(msg)

    def _process_telemetry(self, msg: TelemetryMessage) -> None:
        had_fault = msg.fault_flag is not None
        self.registry.record_telemetry(
            device_id=msg.device_id,
            site=msg.site,
            firmware_version=msg.firmware_version,
            metric_type=msg.metric_type,
            value=msg.value,
            had_fault=had_fault,
        )

        if msg.value is not None:
            self.aggregator.add_sample(msg.device_id, msg.metric_type, msg.value)

            alerts = self.rule_engine.evaluate(msg.device_id, msg.metric_type, msg.value)
            for alert in alerts:
                self._raise_alert(alert)

        self.store.insert_telemetry(
            TelemetryRow(
                device_id=msg.device_id,
                metric_type=msg.metric_type,
                site=msg.site,
                value=msg.value,
                lat=msg.lat,
                lon=msg.lon,
                unit=msg.unit,
                fault_flag=msg.fault_flag,
                timestamp=msg.timestamp,
            )
        )
        self.stats["processed_telemetry"] += 1

    def _process_heartbeat(self, msg: HeartbeatMessage) -> None:
        self.registry.record_heartbeat(
            device_id=msg.device_id,
            site=msg.site,
            firmware_version=msg.firmware_version,
            battery_pct=msg.battery_pct,
        )
        self.stats["processed_heartbeats"] += 1

    def _raise_alert(self, alert) -> None:
        logger.warning(
            "ALERT [%s] %s on %s: value=%.2f threshold=%.2f (%s)",
            alert.severity, alert.rule_name, alert.device_id, alert.value, alert.threshold, alert.message,
        )
        self.store.insert_alert(
            AlertRow(
                device_id=alert.device_id,
                rule_name=alert.rule_name,
                metric_type=alert.metric_type,
                value=alert.value,
                threshold=alert.threshold,
                severity=alert.severity,
                message=alert.message,
                timestamp=alert.timestamp,
            )
        )
        with self._alerts_lock:
            self.recent_alerts.append(alert.as_dict())
            self.recent_alerts = self.recent_alerts[-100:]
        self.stats["alerts_raised"] += 1

    def _maintenance_loop(self) -> None:
        offline_check_interval = self.config["device_management"]["offline_check_interval_sec"]
        rotation_check_interval = self.config["storage"]["rotation_check_interval_sec"]
        last_offline_check = 0.0
        last_rotation_check = 0.0

        while not self._stop_event.is_set():
            now = time.monotonic()
            if now - last_offline_check >= offline_check_interval:
                newly_offline = self.registry.sweep_offline_devices()
                for device_id in newly_offline:
                    logger.warning("Device %s marked OFFLINE (heartbeat timeout)", device_id)
                last_offline_check = now

            if now - last_rotation_check >= rotation_check_interval:
                purged = self.store.purge_expired()
                if purged:
                    logger.info("Storage retention: purged %d expired rows", purged)
                last_rotation_check = now

            time.sleep(0.5)

    def status_report(self) -> dict:
        sys_snap = self.system_monitor.snapshot()
        return {
            "gateway_id": self.config["gateway_id"],
            "uptime_sec": round(time.time() - self.stats["started_at"], 1),
            "stats": dict(self.stats),
            "fleet_summary": self.registry.fleet_summary(),
            "buffer": {
                "telemetry_depth": len(self.telemetry_buffer),
                "telemetry_dropped": self.telemetry_buffer.stats.dropped,
                "telemetry_drop_rate": round(self.telemetry_buffer.stats.drop_rate, 4),
            },
            "system": {
                "cpu_percent": sys_snap.cpu_percent,
                "rss_mb": sys_snap.rss_mb,
                "ram_ceiling_mb": sys_snap.ram_ceiling_mb,
                "memory_pressure": sys_snap.memory_pressure,
                "threads": sys_snap.open_threads,
            },
            "storage": self.store.row_counts(),
            "rejected_messages": self.ingestion.rejected_count,
        }
