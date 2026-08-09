"""
Simple threshold rule engine: evaluates each incoming telemetry value
against configured rules (config/gateway.yaml -> rules) and emits Alert
objects for breaches. This is the "gateway processing" logic layer -- the
kind of local edge-side decisioning that avoids round-tripping every
reading to the cloud before an operator is notified of, e.g., an
overcurrent condition on motor-bay-1.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass(frozen=True)
class Rule:
    name: str
    metric_type: str
    condition: str          # "gt" | "lt"
    threshold: float
    severity: str
    message: str


@dataclass
class Alert:
    rule_name: str
    device_id: str
    metric_type: str
    value: float
    threshold: float
    severity: str
    message: str
    timestamp: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "rule_name": self.rule_name,
            "device_id": self.device_id,
            "metric_type": self.metric_type,
            "value": self.value,
            "threshold": self.threshold,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp,
        }


_CONDITIONS: Dict[str, Callable[[float, float], bool]] = {
    "gt": lambda value, threshold: value > threshold,
    "lt": lambda value, threshold: value < threshold,
}


class RuleEngine:
    def __init__(self, rules: List[dict]) -> None:
        self._rules = [Rule(**r) for r in rules]
        self._by_metric: Dict[str, List[Rule]] = {}
        for rule in self._rules:
            self._by_metric.setdefault(rule.metric_type, []).append(rule)

    def evaluate(self, device_id: str, metric_type: str, value: Optional[float]) -> List[Alert]:
        if value is None:
            return []
        alerts = []
        for rule in self._by_metric.get(metric_type, []):
            check = _CONDITIONS[rule.condition]
            if check(value, rule.threshold):
                alerts.append(
                    Alert(
                        rule_name=rule.name,
                        device_id=device_id,
                        metric_type=metric_type,
                        value=value,
                        threshold=rule.threshold,
                        severity=rule.severity,
                        message=rule.message,
                    )
                )
        return alerts

    @property
    def rules(self) -> List[Rule]:
        return list(self._rules)
