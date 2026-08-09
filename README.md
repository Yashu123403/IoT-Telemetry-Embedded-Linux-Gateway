# IoT Sensor Telemetry + Embedded Linux Gateway Simulation

A software-only, laptop-runnable project that simulates a fleet of
industrial IoT sensors publishing telemetry over **real MQTT** to a
gateway process modeled on **embedded Linux gateway** software
architecture — the class of system Mistral Solutions builds for
Industrial IoT Gateway products (Modbus/serial field sensors → embedded
ARM Linux gateway → cloud/web monitoring).

> **No physical hardware required or claimed.** No ESP32, no Raspberry
> Pi, no real sensors. Sensor devices are simulated as Python threads
> publishing physically-plausible synthetic readings. The MQTT transport,
> gateway ingestion, buffering, rule engine, device registry, aggregation,
> and SQLite storage are **real, working code** — see `docs/architecture.md`
> for the exact boundary between what's real and what's simulated.

## Why this project (relevance to Mistral Solutions)

Mistral's Industrial IoT Gateway case studies describe gathering data
from field sensors (Modbus/serial/IEC62056) on an embedded Linux ARM
gateway, buffering/processing it locally, and exposing a web-based GUI
for configuration and monitoring. This project reproduces that pipeline
shape — sensor fleet → MQTT → gateway processing (buffer, rules,
aggregation, device management, storage) → dashboard — as real, tested
Python code, without requiring the physical gateway board.

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

```bash
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

```bash
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

```bash
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

## What is real vs. simulated (read this before an interview)

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

```bash
pytest tests/ -v
```

51 tests: sensors, fault injection, GPS, buffer overflow policies, rule
engine, aggregator, device registry (including offline-timeout
behavior), SQLite storage, pydantic schema validation, MQTT topic
matching, and **two full integration tests** that start the real
embedded broker, run a real sensor node over real MQTT, and verify the
gateway processes/aggregates/alerts/persists/marks-offline correctly.

## Resume bullets (truthful, Mistral-relevant)

- Built a modular Python IoT telemetry gateway simulation using real MQTT
  (embedded `amqtt` broker + `paho-mqtt` clients) to ingest data from a
  simulated 6-device sensor fleet (temperature, humidity, vibration,
  current, GPS) with configurable fault injection (dropout, spike,
  stuck-at), without physical hardware.
- Implemented an embedded-Linux-style gateway processing pipeline:
  pydantic-validated ingestion, a bounded ring buffer with configurable
  overflow policy, a threshold rule engine, windowed aggregation, a
  heartbeat-based device registry, and SQLite storage with retention-based
  rotation — relevant to Mistral's Industrial IoT Gateway product line.
- Built a device management layer (online/offline tracking, firmware
  version, battery level, remote command channel) exposed via both a
  Flask REST API/web dashboard and a `rich` live terminal dashboard.
- Achieved 51/51 passing tests, including full MQTT-broker-backed
  integration tests validating end-to-end telemetry flow, alerting, and
  offline-device detection — not just mocked unit tests.

## Interview questions this project prepares you for

**IoT / protocols**
1. Why MQTT over HTTP polling for sensor telemetry? What do QoS levels
   0/1/2 mean, and which did you use here and why?
2. Walk through what happens in this project when a device stops sending
   heartbeats — how is "offline" detected, and what's the tradeoff in
   your `heartbeat_timeout_sec` value?
3. Why publish telemetry and heartbeats on separate topics
   (`telemetry/+/+` vs `heartbeat/+`) instead of one combined topic?
4. How would you add MQTT QoS 1/2, retained messages, or a Last Will and
   Testament (LWT) to make offline detection push-based instead of
   timeout-based?

**Embedded Linux / gateway design**
5. Why SQLite instead of Postgres/MySQL for the gateway's local storage?
6. Your ingestion buffer is bounded at N messages — what happens when
   it's full, and why did you choose `drop_oldest` vs `drop_newest` as
   the default?
7. How would this architecture change if the gateway needed to also
   speak Modbus RTU/TCP to real field devices instead of MQTT?
8. What would you monitor in production to know the gateway process
   itself is healthy (not just the devices it's tracking)?

**Systems / testing**
9. Your `test_integration_e2e.py` starts a real broker instead of
   mocking MQTT — why is that worth the extra test time?
10. Why is pydantic validation happening at the ingestion boundary
    specifically, rather than deeper in the processing pipeline?
11. How would you extend the rule engine to support rate-of-change
    alerts (e.g. "temperature rose more than 5°C in 60 seconds") instead
    of just static thresholds?

**Mistral-specific**
12. Mistral's Industrial IoT Gateway integrates protocols like Modbus and
    IEC62056 for utility/industrial metering — how would you design this
    gateway's ingestion layer to support multiple protocols
    side-by-side, not just MQTT?
13. How would you validate this simulation-based design against a real
    gateway board once hardware is available, and what would you expect
    to have to change?
