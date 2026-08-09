import pytest

from src.gateway.buffer import TelemetryBuffer


def test_push_and_drain():
    buf = TelemetryBuffer(max_messages=5, overflow_policy="drop_oldest")
    for i in range(3):
        buf.push(i)
    assert len(buf) == 3
    items = buf.drain()
    assert items == [0, 1, 2]
    assert len(buf) == 0


def test_drop_oldest_overflow():
    buf = TelemetryBuffer(max_messages=2, overflow_policy="drop_oldest")
    buf.push("a")
    buf.push("b")
    buf.push("c")  # should evict "a"
    items = buf.drain()
    assert items == ["b", "c"]
    assert buf.stats.dropped == 1


def test_drop_newest_overflow():
    buf = TelemetryBuffer(max_messages=2, overflow_policy="drop_newest")
    buf.push("a")
    buf.push("b")
    accepted = buf.push("c")
    assert accepted is False
    items = buf.drain()
    assert items == ["a", "b"]


def test_partial_drain():
    buf = TelemetryBuffer(max_messages=10)
    for i in range(5):
        buf.push(i)
    first_two = buf.drain(max_items=2)
    assert first_two == [0, 1]
    assert len(buf) == 3


def test_invalid_policy_raises():
    with pytest.raises(ValueError):
        TelemetryBuffer(max_messages=1, overflow_policy="bogus")
