"""Builds a fleet of SensorNode instances from config/devices.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import yaml

from src.sensors.fault_injector import FaultInjector
from src.sensors.gps_sensor import GpsSensor
from src.sensors.scalar_sensors import CurrentSensor, HumiditySensor, TemperatureSensor, VibrationSensor
from src.sensors.sensor_node import SensorNode

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "devices.yaml"

_SENSOR_CLASSES = {
    "temperature": TemperatureSensor,
    "humidity": HumiditySensor,
    "vibration": VibrationSensor,
    "current": CurrentSensor,
}


def load_device_config(config_path: Optional[str] = None) -> dict:
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_fleet(config_path: Optional[str] = None, seed: Optional[int] = None) -> List[SensorNode]:
    cfg = load_device_config(config_path)
    broker = cfg["mqtt_broker"]
    nodes: List[SensorNode] = []

    for i, dev in enumerate(cfg["devices"]):
        fault_cfg = dev.get("fault_profile", {})
        device_seed = (seed + i) if seed is not None else None

        if dev["type"] == "gps":
            fault_injector = FaultInjector(
                dropout_probability=fault_cfg.get("dropout_probability", 0.0),
                spike_probability=fault_cfg.get("spike_probability", 0.0),
                spike_magnitude=0.0,
                stuck_probability=fault_cfg.get("stuck_probability", 0.0),
            )
            sensor = GpsSensor(
                device_id=dev["device_id"],
                start_lat=dev["params"]["start_lat"],
                start_lon=dev["params"]["start_lon"],
                speed_kmh=dev["params"]["speed_kmh"],
                heading_deg=dev["params"]["heading_deg"],
                fault_injector=fault_injector,
                seed=device_seed,
            )
        else:
            sensor_cls = _SENSOR_CLASSES[dev["type"]]
            params = dev["params"]
            # param keys vary by unit suffix (mean_c, mean_pct, mean_mm_s, mean_a) -- normalize
            mean = next(v for k, v in params.items() if k.startswith("mean"))
            noise_std = next(v for k, v in params.items() if k.startswith("noise_std"))
            drift = next(v for k, v in params.items() if k.startswith("drift_per_min"))
            min_v = next(v for k, v in params.items() if k.startswith("min"))
            max_v = next(v for k, v in params.items() if k.startswith("max"))
            spike_mag = next((v for k, v in fault_cfg.items() if k.startswith("spike_magnitude")), 0.0)

            fault_injector = FaultInjector(
                dropout_probability=fault_cfg.get("dropout_probability", 0.0),
                spike_probability=fault_cfg.get("spike_probability", 0.0),
                spike_magnitude=spike_mag,
                stuck_probability=fault_cfg.get("stuck_probability", 0.0),
            )
            sensor = sensor_cls(
                device_id=dev["device_id"],
                mean=mean,
                noise_std=noise_std,
                drift_per_min=drift,
                min_value=min_v,
                max_value=max_v,
                fault_injector=fault_injector,
                seed=device_seed,
            )

        node = SensorNode(
            device_id=dev["device_id"],
            site=dev["site"],
            sensor=sensor,
            publish_interval_sec=dev["publish_interval_sec"],
            firmware_version=dev["firmware_version"],
            mqtt_host=broker["host"],
            mqtt_port=broker["port"],
        )
        nodes.append(node)

    return nodes
