# IoT Sensor Telemetry + Embedded Linux Gateway Simulation

A software-only, laptop-runnable project that simulates a fleet of
industrial IoT sensors publishing telemetry over **real MQTT** to a
gateway process modeled on **embedded Linux gateway** software
architecture (Modbus/serial field sensors → embedded ARM Linux gateway
→ cloud/web monitoring).

> **No physical hardware required or claimed.** No ESP32, no Raspberry
> Pi, no real sensors. Sensor devices are simulated as Python threads
> publishing physically-plausible synthetic readings. The MQTT transport,
> gateway ingestion, buffering, rule engine, device registry, aggregation,
> and SQLite storage are **real, working code** — see `docs/architecture.md`
> for the exact boundary between what's real and what's simulated.

## Features

- **6 simulated sensor types** across a fleet: 2× temperature, humidity,
  vibration, current, GPS tracker — each with configurable noise, drift,
  and fault injection (dropout, spike, stuck-at).
- **Real MQTT transport**: an embedded pure-Python broker (`amqtt`) plus
  real `paho-mqtt` publisher/subscriber clients — genuine sockets, no
  mocking. Works with an external broker (e.g. Mosquitto) too.
- **Embedded-style gateway process**: bounded ingestion buffer with
  configurable overflow policy, threshold rule engine, windowed
  min/max/avg aggregation, device registry with heartbeat-based
  online/offline tracking, SQLite storage with retention/rotation.
- **Device management**: firmware version tracking, battery level,
  remote command channel (e.g. change a device's publish interval live).
- **Two dashboards**: a `rich` live terminal UI, and a Flask web
  dashboard + REST API.
- **51 passing tests**, including full MQTT-broker-backed integration
  tests (not just mocks).

## Project structure

```
iot-telemetry-gateway/
├── config/
│   ├── devices.yaml         # simulated sensor fleet definition
│   └── gateway.yaml         # gateway resource limits, rules, storage
├── src/
│   ├── sensors/              # base/scalar/gps sensors, fault_injector,
│   │                          #   sensor_node, fleet_factory
│   ├── gateway/               # buffer, rule_engine, aggregator,
│   │                          #   device_registry, storage, ingestion,
│   │                          #   embedded_broker, system_monitor,
│   │                          #   gateway_app
│   ├── protocols/             # pydantic schemas, mqtt_client_wrapper, topics
│   ├── utils/                 # logger
│   └── main.py                # CLI entry point
├── dashboard/
│   ├── rest_api.py            # Flask REST API + HTML dashboard
│   └── cli_dashboard.py       # rich terminal dashboard
├── tests/                     # pytest suite (51 tests, incl. e2e)
└── docs/architecture.md
```

## Setup (VS Code, Windows/Linux/Mac)

python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

No external services required — the embedded MQTT broker starts
in-process. Open the folder in VS Code and select the `.venv`
interpreter.

## Quick start

# Full stack (embedded broker + 6 simulated sensors + gateway),
# live terminal dashboard:
python -m src.main --dashboard rich --seed 42

# Same, but a browser dashboard at http://127.0.0.1:8080 :
python -m src.main --dashboard web --seed 42

# Headless run for 20 seconds, then print a final JSON status report:
python -m src.main --dashboard none --headless-seconds 20 --seed 42
```

Ctrl+C to stop (rich/no-timer runs). On shutdown, a full JSON status
report (messages processed, alerts raised, device fleet summary, buffer
drop rate, gateway memory usage, storage row counts) is printed.

### Using an external broker (e.g. Mosquitto) instead of the embedded one

# 1. Run your own broker, e.g.: mosquitto -p 1883
# 2. Point devices.yaml / gateway.yaml at it (default 127.0.0.1:1883 already matches), then:
python -m src.main --external-broker --dashboard rich
```

### Example: forcing an alert

Edit `config/devices.yaml`, set `temp-sensor-01.params.mean_c: 50.0`
(above the `high_temperature` rule's 45.0°C threshold in
`config/gateway.yaml`), then run the app — you'll see `ALERT [critical]
high_temperature` log lines and matching rows in the dashboard's "Recent
alerts" table.

## What is real vs. simulated 

- **Real**: MQTT transport (broker + clients), gateway ingestion
  validation, bounded buffering, rule evaluation, windowed aggregation,
  device registry/heartbeat logic, SQLite persistence with retention,
  the REST API and dashboards.
- **Simulated**: the physical sensors and field devices themselves
  (Python-generated synthetic readings with noise/drift/faults), and the
  "embedded Linux" resource ceiling the gateway process is measured
  against (a real `psutil` RSS reading compared to a configured budget
  standing in for an ARM SoM's memory envelope).

See `docs/architecture.md` for the full component-by-component table.

## Testing

pytest tests/ -v
```

51 tests: sensors, fault injection, GPS, buffer overflow policies, rule
engine, aggregator, device registry (including offline-timeout
behavior), SQLite storage, pydantic schema validation, MQTT topic
matching, and **two full integration tests** that start the real
embedded broker, run a real sensor node over real MQTT, and verify the
gateway processes/aggregates/alerts/persists/marks-offline correctly.

AUTHOR 
YASHU A B

