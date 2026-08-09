from src.protocols.mqtt_client_wrapper import _topic_matches
from src.protocols.topics import command_topic, heartbeat_topic, telemetry_topic


def test_telemetry_topic_format():
    assert telemetry_topic("dev1", "temperature") == "telemetry/dev1/temperature"


def test_heartbeat_topic_format():
    assert heartbeat_topic("dev1") == "heartbeat/dev1"


def test_command_topic_format():
    assert command_topic("dev1") == "command/dev1"


def test_single_level_wildcard_matches():
    assert _topic_matches("telemetry/+/+", "telemetry/dev1/temperature") is True
    assert _topic_matches("heartbeat/+", "heartbeat/dev1") is True


def test_wildcard_does_not_match_wrong_depth():
    assert _topic_matches("heartbeat/+", "heartbeat/dev1/extra") is False
    assert _topic_matches("telemetry/+/+", "telemetry/dev1") is False


def test_exact_topic_match():
    assert _topic_matches("command/dev1", "command/dev1") is True
    assert _topic_matches("command/dev1", "command/dev2") is False


def test_hash_wildcard_matches_multilevel():
    assert _topic_matches("telemetry/#", "telemetry/dev1/temperature") is True
    assert _topic_matches("#", "anything/at/all") is True
