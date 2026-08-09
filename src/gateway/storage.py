"""
Local persistence layer using SQLite -- the standard lightweight,
dependency-free database available on virtually any embedded Linux image
(no separate DB server process needed, matching an ARM Sitara-class
gateway's resource envelope). Implements a retention policy: old rows are
purged past `retention_hours`, mimicking flash-storage-conscious rotation
on a real embedded gateway rather than growing the DB file unbounded.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class TelemetryRow:
    device_id: str
    metric_type: str
    site: str
    value: Optional[float]
    lat: Optional[float]
    lon: Optional[float]
    unit: str
    fault_flag: Optional[str]
    timestamp: float


@dataclass
class AlertRow:
    device_id: str
    rule_name: str
    metric_type: str
    value: float
    threshold: float
    severity: str
    message: str
    timestamp: float


_SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    site TEXT,
    value REAL,
    lat REAL,
    lon REAL,
    unit TEXT,
    fault_flag TEXT,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_telemetry_device_time ON telemetry(device_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_telemetry_time ON telemetry(timestamp);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    value REAL,
    threshold REAL,
    severity TEXT,
    message TEXT,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(timestamp);
"""


class TelemetryStore:
    def __init__(self, db_path: str, retention_hours: float = 24.0) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._retention_hours = retention_hours
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def insert_telemetry(self, row: TelemetryRow) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO telemetry (device_id, metric_type, site, value, lat, lon, unit, fault_flag, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row.device_id, row.metric_type, row.site, row.value, row.lat, row.lon,
                 row.unit, row.fault_flag, row.timestamp),
            )
            self._conn.commit()

    def insert_alert(self, row: AlertRow) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO alerts (device_id, rule_name, metric_type, value, threshold, severity, message, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (row.device_id, row.rule_name, row.metric_type, row.value, row.threshold,
                 row.severity, row.message, row.timestamp),
            )
            self._conn.commit()

    def purge_expired(self) -> int:
        cutoff = time.time() - (self._retention_hours * 3600.0)
        with self._lock:
            cur = self._conn.execute("DELETE FROM telemetry WHERE timestamp < ?", (cutoff,))
            self._conn.execute("DELETE FROM alerts WHERE timestamp < ?", (cutoff,))
            self._conn.commit()
            return cur.rowcount

    def recent_telemetry(self, device_id: Optional[str] = None, limit: int = 100) -> List[dict]:
        with self._lock:
            if device_id:
                cur = self._conn.execute(
                    "SELECT device_id, metric_type, site, value, lat, lon, unit, fault_flag, timestamp "
                    "FROM telemetry WHERE device_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (device_id, limit),
                )
            else:
                cur = self._conn.execute(
                    "SELECT device_id, metric_type, site, value, lat, lon, unit, fault_flag, timestamp "
                    "FROM telemetry ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def recent_alerts(self, limit: int = 50) -> List[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT device_id, rule_name, metric_type, value, threshold, severity, message, timestamp "
                "FROM alerts ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def row_counts(self) -> dict:
        with self._lock:
            telemetry_count = self._conn.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0]
            alert_count = self._conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        return {"telemetry_rows": telemetry_count, "alert_rows": alert_count}

    def close(self) -> None:
        with self._lock:
            self._conn.close()
