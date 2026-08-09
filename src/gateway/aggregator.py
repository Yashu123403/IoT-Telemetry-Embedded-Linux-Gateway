"""
Windowed aggregation: keeps a rolling window of raw readings per
(device_id, metric_type) and computes min/max/avg/count/last on demand.
This is what lets the gateway forward compact per-minute summaries
upstream instead of every raw reading -- a standard edge-gateway pattern
for constrained/metered backhaul links.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Tuple


@dataclass
class AggregateStats:
    device_id: str
    metric_type: str
    count: int
    min_value: float
    max_value: float
    avg_value: float
    last_value: float
    window_sec: float

    def as_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "metric_type": self.metric_type,
            "count": self.count,
            "min": round(self.min_value, 3),
            "max": round(self.max_value, 3),
            "avg": round(self.avg_value, 3),
            "last": round(self.last_value, 3),
            "window_sec": self.window_sec,
        }


class WindowedAggregator:
    def __init__(self, window_sec: float = 30.0) -> None:
        self._window_sec = window_sec
        self._data: Dict[Tuple[str, str], Deque[Tuple[float, float]]] = defaultdict(deque)
        self._lock = threading.Lock()

    def add_sample(self, device_id: str, metric_type: str, value: float) -> None:
        key = (device_id, metric_type)
        now = time.monotonic()
        with self._lock:
            dq = self._data[key]
            dq.append((now, value))
            self._evict_old(dq, now)

    def _evict_old(self, dq: Deque[Tuple[float, float]], now: float) -> None:
        cutoff = now - self._window_sec
        while dq and dq[0][0] < cutoff:
            dq.popleft()

    def stats_for(self, device_id: str, metric_type: str) -> AggregateStats | None:
        key = (device_id, metric_type)
        now = time.monotonic()
        with self._lock:
            dq = self._data.get(key)
            if not dq:
                return None
            self._evict_old(dq, now)
            if not dq:
                return None
            values = [v for _, v in dq]
            return AggregateStats(
                device_id=device_id,
                metric_type=metric_type,
                count=len(values),
                min_value=min(values),
                max_value=max(values),
                avg_value=sum(values) / len(values),
                last_value=values[-1],
                window_sec=self._window_sec,
            )

    def all_stats(self) -> List[AggregateStats]:
        now = time.monotonic()
        results = []
        with self._lock:
            for (device_id, metric_type), dq in self._data.items():
                self._evict_old(dq, now)
                if not dq:
                    continue
                values = [v for _, v in dq]
                results.append(
                    AggregateStats(
                        device_id=device_id,
                        metric_type=metric_type,
                        count=len(values),
                        min_value=min(values),
                        max_value=max(values),
                        avg_value=sum(values) / len(values),
                        last_value=values[-1],
                        window_sec=self._window_sec,
                    )
                )
        return results
