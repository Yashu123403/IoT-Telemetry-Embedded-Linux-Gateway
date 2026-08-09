"""
Monitors the gateway process's own real CPU/RAM usage (via psutil) and
compares it against the configured `ram_ceiling_mb`, which models the
memory budget of a resource-constrained embedded Linux gateway (e.g. a
Sitara-class ARM SoM with a few hundred MB available to the application
after the OS and other services). This is a REAL measurement of the host
process; the ceiling it's compared against is a SIMULATED budget standing
in for the embedded target.
"""

from __future__ import annotations

from dataclasses import dataclass

import psutil


@dataclass
class SystemSnapshot:
    cpu_percent: float
    rss_mb: float
    ram_ceiling_mb: float
    memory_pressure: bool
    open_threads: int


class SystemMonitor:
    def __init__(self, ram_ceiling_mb: float) -> None:
        self._process = psutil.Process()
        self._ram_ceiling_mb = ram_ceiling_mb
        self._process.cpu_percent(interval=None)  # prime the internal counter

    def snapshot(self) -> SystemSnapshot:
        rss_mb = self._process.memory_info().rss / (1024 * 1024)
        return SystemSnapshot(
            cpu_percent=self._process.cpu_percent(interval=None),
            rss_mb=round(rss_mb, 1),
            ram_ceiling_mb=self._ram_ceiling_mb,
            memory_pressure=rss_mb > self._ram_ceiling_mb,
            open_threads=self._process.num_threads(),
        )
