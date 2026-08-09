"""Live-refreshing terminal dashboard using `rich`, for running the demo
over SSH or without a browser."""

from __future__ import annotations

import time

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from src.gateway.gateway_app import GatewayApp


def _build_layout(gateway: GatewayApp) -> Layout:
    status = gateway.status_report()

    header = Panel(
        f"[bold]{status['gateway_id']}[/bold]  |  uptime {status['uptime_sec']}s  |  "
        f"processed {status['stats']['processed_telemetry']} telemetry, "
        f"{status['stats']['processed_heartbeats']} heartbeats  |  "
        f"alerts {status['stats']['alerts_raised']}  |  "
        f"RSS {status['system']['rss_mb']}/{status['system']['ram_ceiling_mb']} MB"
        + ("  [red bold]MEMORY PRESSURE[/red bold]" if status["system"]["memory_pressure"] else ""),
        title="Embedded Linux Gateway Simulation",
    )

    devices_table = Table(title="Devices", expand=True)
    for col in ("Device", "Site", "Status", "Last Metric", "Last Value", "Battery %", "Faults"):
        devices_table.add_column(col)
    for d in gateway.registry.all_devices():
        status_style = "green" if d.status == "online" else "red"
        devices_table.add_row(
            d.device_id, d.site, f"[{status_style}]{d.status}[/{status_style}]",
            str(d.last_metric_type), str(d.last_value), str(d.battery_pct), str(d.fault_count),
        )

    alerts_table = Table(title="Recent Alerts", expand=True)
    for col in ("Device", "Rule", "Severity", "Value", "Message"):
        alerts_table.add_column(col)
    for a in list(reversed(gateway.recent_alerts))[:10]:
        sev_style = "red bold" if a["severity"] == "critical" else "yellow"
        alerts_table.add_row(
            a["device_id"], a["rule_name"], f"[{sev_style}]{a['severity']}[/{sev_style}]",
            f"{a['value']:.2f}", a["message"],
        )

    layout = Layout()
    layout.split_column(
        Layout(header, size=3),
        Layout(devices_table),
        Layout(alerts_table),
    )
    return layout


def run_dashboard(gateway: GatewayApp, refresh_hz: float = 2.0) -> None:
    console = Console()
    try:
        with Live(_build_layout(gateway), console=console, refresh_per_second=refresh_hz) as live:
            while True:
                time.sleep(1.0 / refresh_hz)
                live.update(_build_layout(gateway))
    except KeyboardInterrupt:
        pass
