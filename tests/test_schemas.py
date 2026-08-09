import pytest
from pydantic import ValidationError

from src.protocols.schemas import DeviceCommand, HeartbeatMessage, TelemetryMessage


def test_valid_telemetry_message():
    msg = TelemetryMessage(
        device_id="t1", metric_type="temperature", site="a",
        value=22.5, unit="C", firmware_version="1.0.0",
    )
    assert msg.device_id == "t1"
    assert msg.sequence == 0


def test_missing_required_field_raises():
    with pytest.raises(ValidationError):
        TelemetryMessage(metric_type="temperature", site="a", unit="C", firmware_version="1.0.0")  # type: ignore[call-arg]


def test_heartbeat_message_optional_battery():
    hb = HeartbeatMessage(device_id="d1", site="a", firmware_version="1.0.0")
    assert hb.battery_pct is None


def test_device_command_defaults():
    cmd = DeviceCommand(device_id="d1", command="reboot")
    assert cmd.payload == {}


def test_gps_telemetry_message_with_lat_lon():
    msg = TelemetryMessage(
        device_id="gps1", metric_type="gps", site="fleet",
        lat=12.97, lon=77.59, unit="deg", firmware_version="3.0.0",
    )
    assert msg.lat == 12.97
    assert msg.value is None
