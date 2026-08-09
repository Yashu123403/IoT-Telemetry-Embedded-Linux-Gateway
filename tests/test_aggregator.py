import time

from src.gateway.aggregator import WindowedAggregator


def test_basic_aggregation():
    agg = WindowedAggregator(window_sec=10.0)
    agg.add_sample("d1", "temperature", 20.0)
    agg.add_sample("d1", "temperature", 22.0)
    agg.add_sample("d1", "temperature", 24.0)
    stats = agg.stats_for("d1", "temperature")
    assert stats.count == 3
    assert stats.min_value == 20.0
    assert stats.max_value == 24.0
    assert abs(stats.avg_value - 22.0) < 1e-9
    assert stats.last_value == 24.0


def test_missing_key_returns_none():
    agg = WindowedAggregator(window_sec=10.0)
    assert agg.stats_for("unknown", "temperature") is None


def test_old_samples_evicted_outside_window():
    agg = WindowedAggregator(window_sec=0.05)
    agg.add_sample("d1", "temperature", 10.0)
    time.sleep(0.1)
    agg.add_sample("d1", "temperature", 99.0)
    stats = agg.stats_for("d1", "temperature")
    assert stats.count == 1
    assert stats.last_value == 99.0


def test_separate_keys_do_not_interfere():
    agg = WindowedAggregator(window_sec=10.0)
    agg.add_sample("d1", "temperature", 20.0)
    agg.add_sample("d2", "humidity", 55.0)
    assert agg.stats_for("d1", "temperature").count == 1
    assert agg.stats_for("d2", "humidity").count == 1
    assert agg.stats_for("d1", "humidity") is None


def test_all_stats_returns_every_active_key():
    agg = WindowedAggregator(window_sec=10.0)
    agg.add_sample("d1", "temperature", 20.0)
    agg.add_sample("d2", "humidity", 55.0)
    results = agg.all_stats()
    keys = {(s.device_id, s.metric_type) for s in results}
    assert ("d1", "temperature") in keys
    assert ("d2", "humidity") in keys
