"""
Device management: tracks every device the gateway has seen, its last
telemetry/heartbeat time, online/offline status (heartbeat-timeout based),
firmware version, and battery level. This is the gateway-side half of
"device management" -- the registry a real IoT gateway UI/API would query
to show fleet health, matching the "Web based GUI for Configuration and
Monitoring" requirement in Mistral's Modular Industrial Gateway case study.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DeviceRecord:
    device_id: str
    site: str = ""
    firmware_version: str = ""
    last_seen: float = field(default_factory=time.time)
    last_metric_type: Optional[str] = None
    last_value: Optional[float] = None
    battery_pct: Optional[float] = None
    message_count: int = 0
    fault_count: int = 0
    status: str = "online"

    def as_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "site": self.site,
            "firmware_version": self.firmware_version,
            "last_seen": self.last_seen,
            "seconds_since_last_seen": round(time.time() - self.last_seen, 1),
            "last_metric_type": self.last_metric_type,
            "last_value": self.last_value,
            "battery_pct": self.battery_pct,
            "message_count": self.message_count,
            "fault_count": self.fault_count,
            "status": self.status,
        }


class DeviceRegistry:
    def __init__(self, heartbeat_timeout_sec: float = 12.0) -> None:
        self._timeout = heartbeat_timeout_sec
        self._devices: Dict[str, DeviceRecord] = {}
        self._lock = threading.Lock()

    def record_telemetry(self, device_id: str, site: str, firmware_version: str,
                          metric_type: str, value: Optional[float], had_fault: bool) -> None:
        with self._lock:
            rec = self._devices.setdefault(device_id, DeviceRecord(device_id=device_id))
            rec.site = site
            rec.firmware_version = firmware_version
            rec.last_seen = time.time()
            rec.last_metric_type = metric_type
            rec.last_value = value
            rec.message_count += 1
            rec.status = "online"
            if had_fault:
                rec.fault_count += 1

    def record_heartbeat(self, device_id: str, site: str, firmware_version: str,
                          battery_pct: Optional[float]) -> None:
        with self._lock:
            rec = self._devices.setdefault(device_id, DeviceRecord(device_id=device_id))
            rec.site = site
            rec.firmware_version = firmware_version
            rec.last_seen = time.time()
            rec.battery_pct = battery_pct
            rec.status = "online"

    def sweep_offline_devices(self) -> List[str]:
        """Marks devices offline if no message has arrived within the
        heartbeat timeout. Returns the list of device_ids newly marked
        offline in this sweep (useful for alerting)."""
        newly_offline = []
        now = time.time()
        with self._lock:
            for rec in self._devices.values():
                if rec.status == "online" and (now - rec.last_seen) > self._timeout:
                    rec.status = "offline"
                    newly_offline.append(rec.device_id)
        return newly_offline

    def get(self, device_id: str) -> Optional[DeviceRecord]:
        with self._lock:
            return self._devices.get(device_id)

    def all_devices(self) -> List[DeviceRecord]:
        with self._lock:
            return list(self._devices.values())

    def fleet_summary(self) -> dict:
        with self._lock:
            devices = list(self._devices.values())
        online = sum(1 for d in devices if d.status == "online")
        return {
            "total_devices": len(devices),
            "online": online,
            "offline": len(devices) - online,
            "total_messages": sum(d.message_count for d in devices),
            "total_faults": sum(d.fault_count for d in devices),
        }
