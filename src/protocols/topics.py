"""Central place for MQTT topic naming so publishers/subscribers agree."""

from __future__ import annotations


def telemetry_topic(device_id: str, metric_type: str) -> str:
    return f"telemetry/{device_id}/{metric_type}"


def heartbeat_topic(device_id: str) -> str:
    return f"heartbeat/{device_id}"


def command_topic(device_id: str) -> str:
    return f"command/{device_id}"


TELEMETRY_WILDCARD = "telemetry/+/+"
HEARTBEAT_WILDCARD = "heartbeat/+"
COMMAND_WILDCARD = "command/+"
