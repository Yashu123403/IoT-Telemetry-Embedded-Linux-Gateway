from __future__ import annotations
import time
import pytest
from src.gateway.embedded_broker import EmbeddedBroker, wait_for_broker_ready
from src.gateway.gateway_app import GatewayApp
from src.sensors.fault_injector import FaultInjector
from src.sensors.scalar_sensors import TemperatureSensor
from src.sensors.sensor_node import SensorNode
BROKER_PORT = 18901

@pytest.fixture()
def broker():
  b = EmbeddedBroker(host="127.0.0.1", port=BROKER_PORT)
  b.start()

  assert wait_for_broker_ready(
    "127.0.0.1",
    BROKER_PORT,
    timeout_sec=5.0,
  )

  yield b

  b.stop()


@pytest.fixture()
def gateway_config_path(tmp_path):
  sqlite_path = (tmp_path / "telemetry.db").as_posix()

  content = f"""

  gateway:
    gateway_id: "test-gw"

    mqtt_broker:
    host: "127.0.0.1"
    port: {BROKER_PORT}
    keepalive: 30
    subscribe_topic: "telemetry/+/+"

  resource_limits:
    ram_ceiling_mb: 256
    buffer_max_messages: 100
    buffer_overflow_policy: "drop_oldest"

  device_management:
    heartbeat_timeout_sec: 5.0
    offline_check_interval_sec: 1.0

  aggregation:
    window_sec: 10.0

  storage:
    sqlite_path: "{sqlite_path}"
    retention_hours: 24
    rotation_check_interval_sec: 60

  rules:
    - name: "high_temperature"
      metric_type: "temperature"
      condition: "gt"
      threshold: 45.0
      severity: "critical"
      message: "Too hot"

  rest_api:
    host: "127.0.0.1"
    port: 8099
"""

  path = tmp_path / "gateway.yaml"
  path.write_text(content, encoding="utf-8")

  return str(path)


def test_telemetry_flows_end_to_end(broker, gateway_config_path):
  gateway = GatewayApp(gateway_config_path)
  gateway.start()

  sensor = TemperatureSensor(
      device_id="hot-sensor",
      mean=50.0,
      noise_std=0.0,
      drift_per_min=0.0,
      min_value=-10,
      max_value=85,
      fault_injector=FaultInjector(),
  )

  node = SensorNode(
      device_id="hot-sensor",
      site="test-site",
      sensor=sensor,
      publish_interval_sec=0.2,
      firmware_version="1.0.0",
      mqtt_host="127.0.0.1",
      mqtt_port=BROKER_PORT,
  )

  node.start()

  try:
      time.sleep(1.5)

      report = gateway.status_report()

      assert report["stats"]["processed_telemetry"] > 0
      assert report["stats"]["alerts_raised"] > 0
      assert report["fleet_summary"]["total_devices"] == 1
      assert report["fleet_summary"]["online"] == 1

      recent = gateway.store.recent_telemetry(
        device_id="hot-sensor",
        limit=10,
      )

      assert len(recent) > 0
      assert recent[0]["value"] == 50.0

      alerts = gateway.store.recent_alerts(limit=10)

      assert len(alerts) > 0
      assert alerts[0]["rule_name"] == "high_temperature"

  finally:
    node.stop()
    gateway.stop()

  def test_offline_detection_end_to_end(broker, gateway_config_path):
    gateway = GatewayApp(gateway_config_path)
    gateway.start()

    sensor = TemperatureSensor(
        device_id="flaky-sensor",
        mean=20.0,
        noise_std=0.0,
        drift_per_min=0.0,
        min_value=-10,
        max_value=85,
    )

    node = SensorNode(
        device_id="flaky-sensor",
        site="test-site",
        sensor=sensor,
        publish_interval_sec=0.2,
        firmware_version="1.0.0",
        mqtt_host="127.0.0.1",
        mqtt_port=BROKER_PORT,
    )

    node.start()

    try:
      time.sleep(0.5)
      node.stop()
      time.sleep(6.0)
      rec = gateway.registry.get("flaky-sensor")
      assert rec is not None
      assert rec.status == "offline"

    finally:
      gateway.stop()
