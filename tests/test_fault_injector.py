import random

from src.sensors.fault_injector import FaultInjector


def test_no_faults_when_probabilities_zero():
    injector = FaultInjector(rng=random.Random(1))
    for _ in range(50):
        outcome = injector.evaluate()
        assert outcome.dropout is False
        assert outcome.stuck is False
        assert outcome.spike_delta == 0.0
        assert outcome.fault_flag is None


def test_dropout_always_triggers_when_probability_one():
    injector = FaultInjector(dropout_probability=1.0, rng=random.Random(2))
    outcome = injector.evaluate()
    assert outcome.dropout is True
    assert outcome.fault_flag == "dropout"


def test_spike_delta_has_correct_magnitude():
    injector = FaultInjector(spike_probability=1.0, spike_magnitude=5.0, rng=random.Random(3))
    outcome = injector.evaluate()
    assert abs(outcome.spike_delta) == 5.0
    assert outcome.fault_flag == "spike"


def test_stuck_state_persists_until_cleared():
    injector = FaultInjector(stuck_probability=1.0, rng=random.Random(4))
    outcome1 = injector.evaluate()
    assert outcome1.stuck is True
    injector.remember_stuck_value(42.0)
    assert injector.stuck_value == 42.0
    injector.clear_stuck()
    assert injector.stuck_value is None


def test_remember_stuck_value_only_sets_once():
    injector = FaultInjector()
    injector.remember_stuck_value(10.0)
    injector.remember_stuck_value(99.0)
    assert injector.stuck_value == 10.0
