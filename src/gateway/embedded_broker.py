"""
Runs a local, pure-Python MQTT broker (via the `amqtt` package) in a
background thread with its own asyncio event loop. This lets the whole
project -- sensors, gateway -- run against a real MQTT broker on
127.0.0.1 without requiring the user to separately install/run Mosquitto
or any other external service. This mirrors how a real Industrial IoT
Gateway sometimes hosts its own local broker for on-prem device
connectivity before bridging upstream.

If the user prefers a real Mosquitto install, that also works unmodified
-- just don't start this embedded broker and point devices.yaml /
gateway.yaml at the external broker's host:port instead (see README).
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from amqtt.broker import Broker
    _AMQTT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _AMQTT_AVAILABLE = False


class EmbeddedBroker:
    """Starts/stops a local amqtt MQTT broker on its own thread+event loop."""

    def __init__(self, host: str = "127.0.0.1", port: int = 1883) -> None:
        if not _AMQTT_AVAILABLE:
            raise ImportError(
                "amqtt is not installed. Run `pip install amqtt`, or run an "
                "external broker (e.g. Mosquitto) and skip EmbeddedBroker."
            )
        self._host = host
        self._port = port
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._broker: Optional["Broker"] = None
        self._ready = threading.Event()

    def _config(self) -> dict:
        return {
            "listeners": {
                "default": {
                    "type": "tcp",
                    "bind": f"{self._host}:{self._port}",
                }
            },
            "sys_interval": 0,
            "auth": {"allow-anonymous": True},
        }

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="embedded-mqtt-broker")
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise TimeoutError("Embedded MQTT broker did not start within 5s")
        logger.info("Embedded MQTT broker listening on %s:%d", self._host, self._port)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def _start_and_signal():
            # Broker must be constructed inside the running loop: it calls
            # asyncio.get_running_loop() internally when no loop is passed.
            self._broker = Broker(self._config())
            await self._broker.start()
            self._ready.set()

        self._loop.create_task(_start_and_signal())
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    def stop(self) -> None:
        if self._loop is None or self._broker is None:
            return

        async def _shutdown():
            await self._broker.shutdown()

        fut = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
        try:
            fut.result(timeout=5.0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error shutting down embedded broker: %s", exc)
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("Embedded MQTT broker stopped")


def wait_for_broker_ready(host: str, port: int, timeout_sec: float = 5.0) -> bool:
    """Polls a TCP connect until the broker accepts connections or timeout."""
    import socket

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False
