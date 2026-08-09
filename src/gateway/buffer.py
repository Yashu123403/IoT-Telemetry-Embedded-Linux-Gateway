"""
Bounded ingestion buffer: models the small in-memory queue an embedded
Linux gateway process would use between the MQTT ingestion callback and
the processing loop (rule engine / aggregation / storage). Under load, or
if the processing loop stalls, something has to give -- this buffer makes
that trade-off explicit instead of growing unbounded and eventually OOM
killing the gateway process, which is exactly the failure mode a resource-
constrained ARM gateway has to be designed to avoid.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, List, Optional


@dataclass
class BufferStats:
    pushed: int = 0
    dropped: int = 0
    max_depth_seen: int = 0

    @property
    def drop_rate(self) -> float:
        return (self.dropped / self.pushed) if self.pushed else 0.0


class TelemetryBuffer:
    def __init__(self, max_messages: int, overflow_policy: str = "drop_oldest") -> None:
        if overflow_policy not in ("drop_oldest", "drop_newest"):
            raise ValueError("overflow_policy must be 'drop_oldest' or 'drop_newest'")
        self._q: Deque[Any] = deque()
        self._max = max_messages
        self._policy = overflow_policy
        self._lock = threading.Lock()
        self.stats = BufferStats()

    def push(self, item: Any) -> bool:
        with self._lock:
            self.stats.pushed += 1
            if len(self._q) >= self._max:
                self.stats.dropped += 1
                if self._policy == "drop_newest":
                    return False
                self._q.popleft()
            self._q.append(item)
            self.stats.max_depth_seen = max(self.stats.max_depth_seen, len(self._q))
            return True

    def drain(self, max_items: Optional[int] = None) -> List[Any]:
        with self._lock:
            if max_items is None:
                items = list(self._q)
                self._q.clear()
                return items
            items = []
            for _ in range(min(max_items, len(self._q))):
                items.append(self._q.popleft())
            return items

    def __len__(self) -> int:
        return len(self._q)
