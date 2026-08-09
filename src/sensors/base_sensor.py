"""
BaseSensor implements a bounded random-walk-with-drift value generator,
shared by all scalar sensor types (temperature, humidity, vibration,
current). Each concrete sensor subclass just supplies its physical
parameters (mean, noise, drift, bounds, unit) via config.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional

from src.sensors.fault_injector import FaultInjector


@dataclass
class SensorReading:
    value: float
    unit: str
    fault_flag: Optional[str]
    timestamp: float


class BaseSensor:
    metric_type: str = "base"
    unit: str = ""

    def __init__(
        self,
        device_id: str,
        mean: float,
        noise_std: float,
        drift_per_min: float,
        min_value: float,
        max_value: float,
        fault_injector: Optional[FaultInjector] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.device_id = device_id
        self._mean = mean
        self._noise_std = noise_std
        self._drift_per_min = drift_per_min
        self._min_value = min_value
        self._max_value = max_value
        self._fault_injector = fault_injector or FaultInjector()
        self._rng = random.Random(seed)
        self._current = mean
        self._start_time = time.monotonic()

    def _apply_drift(self) -> None:
        elapsed_min = (time.monotonic() - self._start_time) / 60.0
        self._mean_with_drift = self._mean + self._drift_per_min * elapsed_min

    def read(self) -> Optional[SensorReading]:
        """Returns a SensorReading, or None if this tick was dropped
        (fault-injected dropout -- no message should be published)."""
        outcome = self._fault_injector.evaluate()

        if outcome.dropout:
            return None

        self._apply_drift()

        if outcome.stuck:
            if self._fault_injector.stuck_value is None:
                self._fault_injector.remember_stuck_value(self._current)
            value = self._fault_injector.stuck_value
        else:
            noise = self._rng.gauss(0, self._noise_std)
            value = self._mean_with_drift + noise + outcome.spike_delta
            value = max(self._min_value, min(self._max_value, value))
            self._current = value

        return SensorReading(
            value=round(value, 3),
            unit=self.unit,
            fault_flag=outcome.fault_flag,
            timestamp=time.time(),
        )
