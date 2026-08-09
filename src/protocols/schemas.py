"""
Wire-format schemas for everything published over MQTT between simulated
sensor nodes and the gateway. Using pydantic gives us real payload
validation on the gateway side (a real embedded gateway has to defend
against malformed/corrupt field data), not just a bag of dict keys.
"""

from __future__ import annotations

import time
from typing import Optional

from pydantic import BaseModel, Field


class TelemetryMessage(BaseModel):
    device_id: str
    metric_type: str            # "temperature" | "humidity" | "vibration" | "current" | "gps"
    site: str
    value: Optional[float] = None       # scalar metrics
    lat: Optional[float] = None         # gps only
    lon: Optional[float] = None         # gps only
    unit: str
    firmware_version: str
    timestamp: float = Field(default_factory=time.time)
    sequence: int = 0
    fault_flag: Optional[str] = None    # "dropout" | "spike" | "stuck" | None


class HeartbeatMessage(BaseModel):
    device_id: str
    site: str
    firmware_version: str
    timestamp: float = Field(default_factory=time.time)
    battery_pct: Optional[float] = None


class DeviceCommand(BaseModel):
    """Gateway -> device control-plane message (device management)."""
    device_id: str
    command: str                 # "set_interval" | "reboot" | "update_firmware"
    payload: dict = Field(default_factory=dict)
    issued_at: float = Field(default_factory=time.time)
