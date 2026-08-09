"""
GPS tracker sensor: simulates a device moving at roughly constant speed
along a heading, with small positional jitter. Separate from BaseSensor
since it produces a (lat, lon) pair rather than a scalar.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Optional

from src.sensors.fault_injector import FaultInjector

_EARTH_RADIUS_KM = 6371.0


@dataclass
class GpsReading:
    lat: float
    lon: float
    fault_flag: Optional[str]
    timestamp: float


class GpsSensor:
    metric_type = "gps"
    unit = "deg"

    def __init__(
        self,
        device_id: str,
        start_lat: float,
        start_lon: float,
        speed_kmh: float,
        heading_deg: float,
        fault_injector: Optional[FaultInjector] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.device_id = device_id
        self._lat = start_lat
        self._lon = start_lon
        self._speed_kmh = speed_kmh
        self._heading_rad = math.radians(heading_deg)
        self._fault_injector = fault_injector or FaultInjector()
        self._rng = random.Random(seed)
        self._last_tick = time.monotonic()

    def read(self) -> Optional[GpsReading]:
        outcome = self._fault_injector.evaluate()
        if outcome.dropout:
            return None

        now = time.monotonic()
        elapsed_h = (now - self._last_tick) / 3600.0
        self._last_tick = now

        if not outcome.stuck:
            distance_km = self._speed_kmh * elapsed_h
            dlat = (distance_km / _EARTH_RADIUS_KM) * math.cos(self._heading_rad)
            dlon = (
                (distance_km / _EARTH_RADIUS_KM)
                * math.sin(self._heading_rad)
                / math.cos(math.radians(self._lat))
            )
            self._lat += math.degrees(dlat) + self._rng.gauss(0, 0.00003)
            self._lon += math.degrees(dlon) + self._rng.gauss(0, 0.00003)

        return GpsReading(
            lat=round(self._lat, 6),
            lon=round(self._lon, 6),
            fault_flag=outcome.fault_flag,
            timestamp=time.time(),
        )
