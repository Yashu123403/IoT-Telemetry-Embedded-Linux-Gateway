#!/usr/bin/env python3
"""
IoT Sensor Telemetry + Embedded Linux Gateway Simulation
---------------------------------------------------------------------------
Entry point. Run from the project root:

    python -m src.main                          # everything, rich terminal dashboard
    python -m src.main --dashboard web           # everything, Flask web dashboard on :8080
    python -m src.main --dashboard none --headless-seconds 30   # run headless for 30s, print summary

    python -m src.main --external-broker         # use an already-running Mosquitto/broker
                                                    #   instead of the embedded one (see README)

See README.md for full setup. Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import sys
import time

from src.gateway.embedded_broker import EmbeddedBroker, wait_for_broker_ready
from src.gateway.gateway_app import GatewayApp, load_gateway_config
from src.sensors.fleet_factory import build_fleet, load_device_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--devices-config", default=None, help="Path to devices.yaml")
    parser.add_argument("--gateway-config", default=None, help="Path to gateway.yaml")
    parser.add_argument("--dashboard", choices=["rich", "web", "none"], default="rich",
                         help="Dashboard mode: 'rich' terminal UI, 'web' Flask dashboard, or 'none' for headless.")
    parser.add_argument("--external-broker", action="store_true",
                         help="Do not start the embedded amqtt broker; connect to the broker "
                              "configured in devices.yaml/gateway.yaml instead (e.g. an already-running Mosquitto).")
    parser.add_argument("--headless-seconds", type=float, default=None,
                         help="With --dashboard none, run for N seconds then print a final status report and exit. "
                              "If omitted, runs until Ctrl+C.")
    parser.add_argument("--seed", type=int, default=None, help="Seed for reproducible sensor readings.")
    return parser


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    device_cfg = load_device_config(args.devices_config)
    gateway_cfg = load_gateway_config(args.gateway_config)
    broker_cfg = device_cfg["mqtt_broker"]

    embedded_broker = None
    if not args.external_broker:
        embedded_broker = EmbeddedBroker(host=broker_cfg["host"], port=broker_cfg["port"])
        embedded_broker.start()
        if not wait_for_broker_ready(broker_cfg["host"], broker_cfg["port"], timeout_sec=5.0):
            logger.error("Embedded broker did not become ready in time.")
            return 1
    else:
        logger.info("Using external broker at %s:%d (make sure it's running)", broker_cfg["host"], broker_cfg["port"])
        if not wait_for_broker_ready(broker_cfg["host"], broker_cfg["port"], timeout_sec=5.0):
            logger.error("Could not reach external broker at %s:%d", broker_cfg["host"], broker_cfg["port"])
            return 1

    gateway = GatewayApp(args.gateway_config)
    gateway.start()

    fleet = build_fleet(args.devices_config, seed=args.seed)
    for node in fleet:
        node.start()
        time.sleep(0.05)  # stagger connections a little, like real devices joining a network

    logger.info("Fleet of %d simulated sensor nodes running against gateway '%s'",
                len(fleet), gateway.config["gateway_id"])

    try:
        if args.dashboard == "rich":
            from dashboard.cli_dashboard import run_dashboard
            run_dashboard(gateway)
        elif args.dashboard == "web":
            from dashboard.rest_api import create_app
            api_cfg = gateway.config["rest_api"]
            app = create_app(gateway)
            logger.info("Web dashboard: http://%s:%d", api_cfg["host"], api_cfg["port"])
            app.run(host=api_cfg["host"], port=api_cfg["port"], debug=False, use_reloader=False)
        else:
            if args.headless_seconds:
                time.sleep(args.headless_seconds)
            else:
                while True:
                    time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Shutting down...")
        import json
        final_report = None
        try:
            final_report = gateway.status_report()
        except Exception:  # noqa: BLE001
            pass

        for node in fleet:
            node.stop()
        gateway.stop()
        if embedded_broker:
            embedded_broker.stop()

        if final_report:
            print(json.dumps(final_report, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
