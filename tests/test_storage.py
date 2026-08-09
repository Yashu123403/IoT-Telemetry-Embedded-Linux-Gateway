import time

from src.gateway.storage import AlertRow, TelemetryRow, TelemetryStore


def test_insert_and_read_telemetry(tmp_path):
    store = TelemetryStore(str(tmp_path / "test.db"), retention_hours=24)
    store.insert_telemetry(
        TelemetryRow(device_id="d1", metric_type="temperature", site="a", value=22.0,
                     lat=None, lon=None, unit="C", fault_flag=None, timestamp=time.time())
    )
    rows = store.recent_telemetry(device_id="d1", limit=10)
    assert len(rows) == 1
    assert rows[0]["value"] == 22.0
    store.close()


def test_insert_and_read_alerts(tmp_path):
    store = TelemetryStore(str(tmp_path / "test.db"))
    store.insert_alert(
        AlertRow(device_id="d1", rule_name="high_temp", metric_type="temperature",
                 value=50.0, threshold=45.0, severity="critical", message="hot", timestamp=time.time())
    )
    alerts = store.recent_alerts(limit=10)
    assert len(alerts) == 1
    assert alerts[0]["rule_name"] == "high_temp"
    store.close()


def test_purge_expired_removes_old_rows(tmp_path):
    store = TelemetryStore(str(tmp_path / "test.db"), retention_hours=0.0000001)
    old_ts = time.time() - 10_000
    store.insert_telemetry(
        TelemetryRow(device_id="d1", metric_type="temperature", site="a", value=22.0,
                     lat=None, lon=None, unit="C", fault_flag=None, timestamp=old_ts)
    )
    purged = store.purge_expired()
    assert purged >= 1
    assert store.row_counts()["telemetry_rows"] == 0
    store.close()


def test_row_counts(tmp_path):
    store = TelemetryStore(str(tmp_path / "test.db"))
    for i in range(3):
        store.insert_telemetry(
            TelemetryRow(device_id="d1", metric_type="temperature", site="a", value=float(i),
                         lat=None, lon=None, unit="C", fault_flag=None, timestamp=time.time())
        )
    counts = store.row_counts()
    assert counts["telemetry_rows"] == 3
    store.close()
