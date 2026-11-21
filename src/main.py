
#!/usr/bin/env python3
"""
IoT Sensor Telemetry + Embedded Linux Gateway Simulation

Run from the project root:

    python -m src.main
    python -m src.main --dashboard web
    python -m src.main --dashboard none --headless-seconds 30
    python -m src.main --external-broker

Press Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from src.gateway.embedded_broker import (
    EmbeddedBroker,
    wait_for_broker_ready,
)
from src.gateway.gateway_app import (
    GatewayApp,
    load_gateway_config,
)
from src.sensors.fleet_factory import (
    build_fleet,
    load_device_config,
)
from src.utils.logger import get_logger


logger = get_logger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--devices-config",
        default=None,
        help="Path to devices.yaml",
    )

    parser.add_argument(
        "--gateway-config",
        default=None,
        help="Path to gateway.yaml",
    )

    parser.add_argument(
        "--dashboard",
        choices=["rich", "web", "none"],
        default="rich",
        help="Dashboard mode: rich, web, or none.",
    )

    parser.add_argument(
        "--external-broker",
        action="store_true",
        help="Use an already-running external MQTT broker.",
    )

    parser.add_argument(
        "--headless-seconds",
        type=float,
        default=None,
        help="Run headless mode for a specified number of seconds.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for reproducible sensor readings.",
    )

    return parser


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    device_cfg = load_device_config(args.devices_config)
    gateway_cfg = load_gateway_config(args.gateway_config)

    broker_cfg = device_cfg["mqtt_broker"]

    embedded_broker = None
    gateway = None
    fleet = []

    try:
        # Start the embedded MQTT broker unless an external broker is used.
        if not args.external_broker:
            embedded_broker = EmbeddedBroker(
                host=broker_cfg["host"],
                port=broker_cfg["port"],
            )

            embedded_broker.start()

            if not wait_for_broker_ready(
                broker_cfg["host"],
                broker_cfg["port"],
                timeout_sec=5.0,
            ):
                logger.error(
                    "Embedded broker did not become ready in time."
                )
                return 1

        else:
            logger.info(
                "Using external broker at %s:%d",
                broker_cfg["host"],
                broker_cfg["port"],
            )

            if not wait_for_broker_ready(
                broker_cfg["host"],
                broker_cfg["port"],
                timeout_sec=5.0,
            ):
                logger.error(
                    "Could not reach external broker at %s:%d",
                    broker_cfg["host"],
                    broker_cfg["port"],
                )
                return 1

        # Start the gateway.
        gateway = GatewayApp(args.gateway_config)
        gateway.start()

        # Start simulated sensor devices.
        fleet = build_fleet(
            args.devices_config,
            seed=args.seed,
        )

        for node in fleet:
            node.start()
            time.sleep(0.05)

        logger.info(
            "Fleet of %d simulated sensor nodes running against gateway '%s'",
            len(fleet),
            gateway.config["gateway_id"],
        )

        # Select dashboard mode.
        if args.dashboard == "rich":
            from dashboard.cli_dashboard import run_dashboard

            run_dashboard(gateway)

        elif args.dashboard == "web":
            from dashboard.rest_api import create_app

            api_cfg = gateway.config["rest_api"]

            app = create_app(gateway)

            # Use Render's assigned port when deployed.
            # Fall back to the configured port for local execution.
            host = os.environ.get("HOST", "0.0.0.0")
            port = int(
                os.environ.get("PORT", api_cfg["port"])
            )

            logger.info(
                "Web dashboard running at http://%s:%d",
                host,
                port,
            )

            app.run(
                host=host,
                port=port,
                debug=False,
                use_reloader=False,
            )

        else:
            if args.headless_seconds is not None:
                time.sleep(args.headless_seconds)
            else:
                while True:
                    time.sleep(1.0)

    except KeyboardInterrupt:
        logger.info("Shutdown requested by user.")

    finally:
        logger.info("Shutting down...")

        final_report = None

        if gateway is not None:
            try:
                final_report = gateway.status_report()
            except Exception:
                logger.exception(
                    "Could not generate final gateway report."
                )

        # Stop all simulated sensor nodes.
        for node in fleet:
            try:
                node.stop()
            except Exception:
                logger.exception("Error stopping a sensor node.")

        # Stop the gateway.
        if gateway is not None:
            try:
                gateway.stop()
            except Exception:
                logger.exception("Error stopping the gateway.")

        # Stop the embedded MQTT broker.
        if embedded_broker is not None:
            try:
                embedded_broker.stop()
            except Exception:
                logger.exception("Error stopping the MQTT broker.")

        if final_report:
            print(json.dumps(final_report, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
