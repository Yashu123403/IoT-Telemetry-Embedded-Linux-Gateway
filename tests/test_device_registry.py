import time

from src.gateway.device_registry import DeviceRegistry


def test_record_telemetry_creates_device():
    registry = DeviceRegistry(heartbeat_timeout_sec=5.0)
    registry.record_telemetry("d1", "site-a", "1.0.0", "temperature", 22.5, had_fault=False)
    rec = registry.get("d1")
    assert rec is not None
    assert rec.site == "site-a"
    assert rec.last_value == 22.5
    assert rec.status == "online"
    assert rec.message_count == 1


def test_fault_count_increments():
    registry = DeviceRegistry()
    registry.record_telemetry("d1", "site-a", "1.0.0", "temperature", 22.5, had_fault=True)
    registry.record_telemetry("d1", "site-a", "1.0.0", "temperature", 23.0, had_fault=False)
    rec = registry.get("d1")
    assert rec.fault_count == 1
    assert rec.message_count == 2


def test_heartbeat_updates_battery():
    registry = DeviceRegistry()
    registry.record_heartbeat("d1", "site-a", "1.0.0", battery_pct=87.5)
    rec = registry.get("d1")
    assert rec.battery_pct == 87.5


def test_sweep_marks_offline_after_timeout():
    registry = DeviceRegistry(heartbeat_timeout_sec=0.05)
    registry.record_telemetry("d1", "site-a", "1.0.0", "temperature", 20.0, had_fault=False)
    time.sleep(0.1)
    newly_offline = registry.sweep_offline_devices()
    assert "d1" in newly_offline
    assert registry.get("d1").status == "offline"


def test_device_comes_back_online_on_new_message():
    registry = DeviceRegistry(heartbeat_timeout_sec=0.05)
    registry.record_telemetry("d1", "site-a", "1.0.0", "temperature", 20.0, had_fault=False)
    time.sleep(0.1)
    registry.sweep_offline_devices()
    assert registry.get("d1").status == "offline"
    registry.record_telemetry("d1", "site-a", "1.0.0", "temperature", 21.0, had_fault=False)
    assert registry.get("d1").status == "online"


def test_fleet_summary():
    registry = DeviceRegistry(heartbeat_timeout_sec=100.0)
    registry.record_telemetry("d1", "site-a", "1.0.0", "temperature", 20.0, had_fault=False)
    registry.record_telemetry("d2", "site-b", "1.0.0", "humidity", 55.0, had_fault=True)
    summary = registry.fleet_summary()
    assert summary["total_devices"] == 2
    assert summary["online"] == 2
    assert summary["total_faults"] == 1
