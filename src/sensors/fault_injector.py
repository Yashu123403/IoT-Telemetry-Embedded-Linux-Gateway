"""
Fault injection for simulated sensors: dropout (message never sent),
spike (implausible one-off reading), stuck-at (repeats last value), and
slow drift (calibration decay over time). This is what makes the gateway
side (rule engine, device registry offline detection, anomaly-worthy
telemetry) actually have something realistic to react to, instead of
clean sine waves.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class FaultOutcome:
    dropout: bool = False
    spike_delta: float = 0.0
    stuck: bool = False
    fault_flag: Optional[str] = None


class FaultInjector:
    def __init__(
        self,
        dropout_probability: float = 0.0,
        spike_probability: float = 0.0,
        spike_magnitude: float = 0.0,
        stuck_probability: float = 0.0,
        rng: Optional[random.Random] = None,
    ) -> None:
        self._p_dropout = dropout_probability
        self._p_spike = spike_probability
        self._spike_magnitude = spike_magnitude
        self._p_stuck = stuck_probability
        self._rng = rng or random.Random()
        self._stuck_active = False
        self._stuck_value: Optional[float] = None

    def evaluate(self) -> FaultOutcome:
        if self._rng.random() < self._p_dropout:
            return FaultOutcome(dropout=True, fault_flag="dropout")

        if self._stuck_active:
            # a stuck sensor recovers with a small per-tick probability,
            # mimicking a transient firmware/bus glitch rather than a
            # permanent hardware failure
            if self._rng.random() < 0.08:
                self.clear_stuck()
            else:
                return FaultOutcome(stuck=True, fault_flag="stuck")

        if self._rng.random() < self._p_stuck:
            self._stuck_active = True
            return FaultOutcome(stuck=True, fault_flag="stuck")

        if self._rng.random() < self._p_spike:
            sign = self._rng.choice([-1, 1])
            return FaultOutcome(spike_delta=sign * self._spike_magnitude, fault_flag="spike")

        return FaultOutcome()

    def clear_stuck(self) -> None:
        self._stuck_active = False
        self._stuck_value = None

    def remember_stuck_value(self, value: float) -> None:
        if self._stuck_value is None:
            self._stuck_value = value

    @property
    def stuck_value(self) -> Optional[float]:
        return self._stuck_value
