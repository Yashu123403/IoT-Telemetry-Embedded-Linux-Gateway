from src.sensors.fault_injector import FaultInjector
from src.sensors.scalar_sensors import CurrentSensor, HumiditySensor, TemperatureSensor, VibrationSensor


def test_temperature_reading_within_bounds():
    sensor = TemperatureSensor(
        device_id="t1", mean=24.0, noise_std=0.5, drift_per_min=0.0,
        min_value=-10.0, max_value=85.0, seed=1,
    )
    for _ in range(100):
        reading = sensor.read()
        assert reading is not None
        assert -10.0 <= reading.value <= 85.0
        assert reading.unit == "C"


def test_reading_clamped_to_max_on_extreme_noise():
    sensor = TemperatureSensor(
        device_id="t2", mean=80.0, noise_std=50.0, drift_per_min=0.0,
        min_value=-10.0, max_value=85.0, seed=2,
    )
    for _ in range(50):
        reading = sensor.read()
        if reading:
            assert reading.value <= 85.0


def test_dropout_returns_none():
    injector = FaultInjector(dropout_probability=1.0)
    sensor = TemperatureSensor(
        device_id="t3", mean=20.0, noise_std=1.0, drift_per_min=0.0,
        min_value=-10, max_value=85, fault_injector=injector,
    )
    assert sensor.read() is None


def test_humidity_and_vibration_and_current_types():
    h = HumiditySensor(device_id="h1", mean=50, noise_std=1, drift_per_min=0, min_value=0, max_value=100, seed=1)
    v = VibrationSensor(device_id="v1", mean=1.0, noise_std=0.1, drift_per_min=0, min_value=0, max_value=50, seed=1)
    c = CurrentSensor(device_id="c1", mean=10, noise_std=0.5, drift_per_min=0, min_value=0, max_value=40, seed=1)
    assert h.read().unit == "%"
    assert v.read().unit == "mm/s"
    assert c.read().unit == "A"


def test_deterministic_with_same_seed():
    s1 = TemperatureSensor(device_id="d1", mean=24, noise_std=1, drift_per_min=0, min_value=-10, max_value=85, seed=7)
    s2 = TemperatureSensor(device_id="d1", mean=24, noise_std=1, drift_per_min=0, min_value=-10, max_value=85, seed=7)
    r1 = s1.read()
    r2 = s2.read()
    assert r1.value == r2.value
