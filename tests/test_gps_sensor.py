import time

from src.sensors.gps_sensor import GpsSensor


def test_gps_moves_over_time():
    sensor = GpsSensor(
        device_id="gps1", start_lat=12.9716, start_lon=77.5946,
        speed_kmh=50.0, heading_deg=90.0, seed=1,
    )
    r1 = sensor.read()
    time.sleep(0.2)
    r2 = sensor.read()
    assert r1 is not None and r2 is not None
    # heading 90 (east) should increase longitude over time
    assert r2.lon >= r1.lon


def test_gps_dropout_returns_none():
    from src.sensors.fault_injector import FaultInjector
    injector = FaultInjector(dropout_probability=1.0)
    sensor = GpsSensor(
        device_id="gps2", start_lat=0.0, start_lon=0.0,
        speed_kmh=10.0, heading_deg=0.0, fault_injector=injector,
    )
    assert sensor.read() is None
