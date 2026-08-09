"""Concrete scalar sensor types. Each is a thin, typed wrapper around
BaseSensor's random-walk generator with the appropriate unit."""

from __future__ import annotations

from src.sensors.base_sensor import BaseSensor


class TemperatureSensor(BaseSensor):
    metric_type = "temperature"
    unit = "C"


class HumiditySensor(BaseSensor):
    metric_type = "humidity"
    unit = "%"


class VibrationSensor(BaseSensor):
    metric_type = "vibration"
    unit = "mm/s"


class CurrentSensor(BaseSensor):
    metric_type = "current"
    unit = "A"
