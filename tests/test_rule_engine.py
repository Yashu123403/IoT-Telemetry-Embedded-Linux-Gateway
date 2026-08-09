from src.gateway.rule_engine import RuleEngine

_RULES = [
    {"name": "high_temp", "metric_type": "temperature", "condition": "gt", "threshold": 45.0,
     "severity": "critical", "message": "too hot"},
    {"name": "low_temp", "metric_type": "temperature", "condition": "lt", "threshold": -5.0,
     "severity": "warning", "message": "too cold"},
]


def test_no_alert_within_bounds():
    engine = RuleEngine(_RULES)
    alerts = engine.evaluate("t1", "temperature", 20.0)
    assert alerts == []


def test_alert_on_high_threshold_breach():
    engine = RuleEngine(_RULES)
    alerts = engine.evaluate("t1", "temperature", 50.0)
    assert len(alerts) == 1
    assert alerts[0].rule_name == "high_temp"
    assert alerts[0].severity == "critical"


def test_alert_on_low_threshold_breach():
    engine = RuleEngine(_RULES)
    alerts = engine.evaluate("t1", "temperature", -10.0)
    assert len(alerts) == 1
    assert alerts[0].rule_name == "low_temp"


def test_no_rules_for_unknown_metric():
    engine = RuleEngine(_RULES)
    alerts = engine.evaluate("h1", "humidity", 200.0)
    assert alerts == []


def test_none_value_produces_no_alerts():
    engine = RuleEngine(_RULES)
    assert engine.evaluate("t1", "temperature", None) == []
