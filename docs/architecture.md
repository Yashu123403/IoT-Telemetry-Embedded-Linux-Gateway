# Architecture — IoT Sensor Telemetry + Embedded Linux Gateway Simulation

## Why this design

Mistral Solutions' Industrial IoT Gateway work centers on embedded Linux
running on ARM SoMs (e.g. TI Sitara-class processors), ingesting field
data over Modbus/serial/IEC62056 from sensors, and forwarding it upstream
with local buffering, device configuration, and a web-based monitoring
GUI. This project reproduces that software architecture end-to-end —
sensor fleet, real MQTT transport, an embedded-style gateway process,
local persistence, and a monitoring dashboard — entirely in Python on a
laptop, with the "embedded" resource constraints modeled explicitly
rather than assumed away.

## Component diagram

```
Simulated Sensor Fleet (src/sensors/)
  - SensorNode per device, own thread
  - fault injection (dropout/spike/stuck/drift)
        |
        |  MQTT (real, over TCP/localhost)
        |  topic: telemetry/<id>/<type>
        |  topic: heartbeat/<id>
        |  topic: command/<id>  (gateway -> device)
        v
EmbeddedBroker (src/gateway/embedded_broker.py)
  amqtt-based, pure-Python MQTT 3.1.1 broker on 127.0.0.1:1883
        |
        v
GatewayApp (src/gateway/gateway_app.py) -- the "embedded Linux gateway process"

  IngestionService (pydantic-validated)
      -> TelemetryBuffer (bounded, drop_oldest/newest)
      -> HeartbeatBuffer

  processing loop (drains buffers):
      -> DeviceRegistry     (online/offline, firmware, battery)
      -> WindowedAggregator (rolling min/max/avg per device/metric)
      -> RuleEngine         (threshold alerts)
      -> TelemetryStore     (SQLite, with retention/rotation)

  maintenance loop: offline sweep, storage rotation
  SystemMonitor: real RSS/CPU vs simulated ram_ceiling_mb
        |
        v
dashboard/rest_api.py (Flask)  +  dashboard/cli_dashboard.py (rich terminal)
```

## The core honesty boundary: real vs. simulated

| Component | Real or simulated | Detail |
|---|---|---|
| MQTT transport | **Real** | An actual MQTT 3.1.1 broker (`amqtt`) and real `paho-mqtt` clients: real sockets, real serialization, real topic routing |
| Sensor readings | **Simulated** | Physically-plausible synthetic values (random walk + drift + fault injection), not real sensor hardware |
| Device fleet | **Simulated** | Python threads standing in for embedded field devices — no ESP32/RPi/physical sensors |
| Gateway processing (buffering, rules, aggregation, registry, storage) | **Real** | Genuine, working software logic — same code would run against a real MQTT-speaking sensor fleet with zero changes to the gateway side |
| SQLite persistence | **Real** | An actual local database file with real retention/rotation logic |
| Gateway resource ceiling (`ram_ceiling_mb`) | **Simulated budget, real measurement** | `psutil` reads the actual host process RSS; the ceiling it's compared against stands in for an embedded ARM gateway's memory budget |
| "Embedded Linux" | **Not claimed** | Runs on the host OS (Windows/Linux/Mac); the gateway's *software architecture* (bounded buffers, local SQLite, systemd-process-style long-running service, resource monitoring) mirrors what would run on embedded Linux, but no embedded OS/kernel is involved |

This project's honest claim: **the gateway software you're looking at is
real, working, and MQTT-integration-tested — the only simulated part is
the physical device fleet generating the input data and the "embedded"
resource budget it's measured against.**

## Data flow per telemetry message

1. A `SensorNode`'s `BaseSensor`/`GpsSensor` generates a reading each
   `publish_interval_sec`, with `FaultInjector` occasionally producing a
   dropout (nothing published), spike, or stuck-at fault.
2. The reading is wrapped in a `TelemetryMessage` (pydantic) and published
   to `telemetry/<device_id>/<metric_type>` on the MQTT broker.
3. `IngestionService`, subscribed to `telemetry/+/+`, receives the
   message on its MQTT network thread, validates it against the pydantic
   schema (malformed payloads are rejected and counted, not crashed on),
   and pushes it onto the bounded `TelemetryBuffer`.
4. The gateway's processing loop drains the buffer (max 50 messages per
   tick) and, per message:
   - updates `DeviceRegistry` (last-seen, status, message/fault counts)
   - adds the value to `WindowedAggregator`
   - runs it through `RuleEngine`; any breach becomes an `Alert`, logged
     and persisted
   - persists the raw reading to `TelemetryStore` (SQLite)
5. A separate maintenance loop periodically sweeps `DeviceRegistry` for
   devices that haven't been heard from within `heartbeat_timeout_sec`
   (marking them offline) and purges `TelemetryStore` rows older than
   `retention_hours`.
6. The Flask REST API / rich terminal dashboard read this same live state
   (`gateway.status_report()`, `gateway.registry`, `gateway.store`) for
   monitoring.

## Why a bounded buffer + drop policy (not an unbounded queue)

A real embedded gateway with ~256MB of usable RAM cannot let an ingestion
queue grow without limit if the processing loop stalls (e.g. during a
slow SQLite write or a burst from many devices). `TelemetryBuffer` makes
this trade-off explicit and testable: `drop_oldest` favors keeping the
freshest state (fine for live telemetry dashboards), `drop_newest`
favors not losing already-buffered work (fine for slower, must-not-skip
processing). `config/gateway.yaml` lets you choose per deployment.

## Why SQLite, not a full DB server

SQLite requires no separate server process, which matches a
resource-constrained embedded Linux image where running a full database
server alongside the gateway application isn't realistic. Retention-based
purging keeps the on-disk footprint bounded, mirroring flash-storage
constraints on embedded targets.
