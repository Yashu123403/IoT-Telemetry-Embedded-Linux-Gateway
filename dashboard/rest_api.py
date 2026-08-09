"""
Minimal REST API + auto-refreshing HTML dashboard exposing the gateway's
device management and monitoring state -- the software equivalent of the
"Web based GUI for Configuration and Monitoring" called out in Mistral's
Modular Industrial Gateway case study. Read-only; no device control beyond
the demonstrated `/api/command/<device_id>` endpoint used for the remote
interval-change interview demo.
"""

from __future__ import annotations

from flask import Flask, jsonify, render_template_string, request

from src.gateway.gateway_app import GatewayApp

_PAGE = """
<!doctype html>
<html>
<head>
  <title>IoT Telemetry Gateway Dashboard</title>
  <meta http-equiv="refresh" content="3">
  <style>
    body { font-family: -apple-system, Segoe UI, sans-serif; background:#0f1115; color:#e6e6e6; margin:0; padding:24px;}
    h1 { font-size: 20px; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(260px,1fr)); gap:16px; margin-bottom:24px;}
    .card { background:#1a1d24; border-radius:8px; padding:16px; }
    .card h3 { margin:0 0 8px 0; font-size:13px; color:#8a8f98; text-transform:uppercase; letter-spacing:.05em;}
    .card .value { font-size:26px; font-weight:600; }
    table { width:100%; border-collapse: collapse; font-size:13px;}
    th, td { text-align:left; padding:6px 8px; border-bottom:1px solid #2a2e37;}
    th { color:#8a8f98; font-weight:500;}
    .online { color:#2ecc71; }
    .offline { color:#e74c3c; }
    .critical { color:#e74c3c; font-weight:600;}
    .warning { color:#f39c12; font-weight:600;}
  </style>
</head>
<body>
  <h1>IoT Telemetry Gateway — {{ status.gateway_id }} (uptime {{ status.uptime_sec }}s)</h1>
  <div class="grid">
    <div class="card"><h3>Devices online</h3><div class="value">{{ status.fleet_summary.online }} / {{ status.fleet_summary.total_devices }}</div></div>
    <div class="card"><h3>Messages processed</h3><div class="value">{{ status.stats.processed_telemetry }}</div></div>
    <div class="card"><h3>Alerts raised</h3><div class="value">{{ status.stats.alerts_raised }}</div></div>
    <div class="card"><h3>Gateway RSS / ceiling</h3><div class="value">{{ status.system.rss_mb }} / {{ status.system.ram_ceiling_mb }} MB</div></div>
    <div class="card"><h3>Buffer drop rate</h3><div class="value">{{ (status.buffer.telemetry_drop_rate * 100) | round(2) }}%</div></div>
    <div class="card"><h3>Rejected messages</h3><div class="value">{{ status.rejected_messages }}</div></div>
  </div>

  <h2>Devices</h2>
  <table>
    <tr><th>Device</th><th>Site</th><th>Status</th><th>Last metric</th><th>Last value</th><th>Battery</th><th>Faults</th></tr>
    {% for d in devices %}
    <tr>
      <td>{{ d.device_id }}</td>
      <td>{{ d.site }}</td>
      <td class="{{ d.status }}">{{ d.status }}</td>
      <td>{{ d.last_metric_type }}</td>
      <td>{{ d.last_value }}</td>
      <td>{{ d.battery_pct }}</td>
      <td>{{ d.fault_count }}</td>
    </tr>
    {% endfor %}
  </table>

  <h2>Recent alerts</h2>
  <table>
    <tr><th>Time</th><th>Device</th><th>Rule</th><th>Severity</th><th>Value</th><th>Message</th></tr>
    {% for a in alerts %}
    <tr>
      <td>{{ a.timestamp | round(1) }}</td>
      <td>{{ a.device_id }}</td>
      <td>{{ a.rule_name }}</td>
      <td class="{{ a.severity }}">{{ a.severity }}</td>
      <td>{{ a.value }}</td>
      <td>{{ a.message }}</td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>
"""


def create_app(gateway: GatewayApp) -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def dashboard():
        status = gateway.status_report()
        devices = [d.as_dict() for d in gateway.registry.all_devices()]
        alerts = list(reversed(gateway.recent_alerts[-30:]))
        return render_template_string(_PAGE, status=status, devices=devices, alerts=alerts)

    @app.route("/api/status")
    def api_status():
        return jsonify(gateway.status_report())

    @app.route("/api/devices")
    def api_devices():
        return jsonify([d.as_dict() for d in gateway.registry.all_devices()])

    @app.route("/api/devices/<device_id>")
    def api_device_detail(device_id: str):
        rec = gateway.registry.get(device_id)
        if rec is None:
            return jsonify({"error": "unknown device"}), 404
        return jsonify(rec.as_dict())

    @app.route("/api/telemetry/recent")
    def api_recent_telemetry():
        device_id = request.args.get("device_id")
        limit = int(request.args.get("limit", 100))
        return jsonify(gateway.store.recent_telemetry(device_id=device_id, limit=limit))

    @app.route("/api/alerts/recent")
    def api_recent_alerts():
        limit = int(request.args.get("limit", 50))
        return jsonify(gateway.store.recent_alerts(limit=limit))

    @app.route("/api/aggregates")
    def api_aggregates():
        return jsonify([s.as_dict() for s in gateway.aggregator.all_stats()])

    @app.route("/api/command/<device_id>", methods=["POST"])
    def api_command(device_id: str):
        body = request.get_json(force=True, silent=True) or {}
        command = body.get("command")
        payload = body.get("payload", {})
        if not command:
            return jsonify({"error": "missing 'command'"}), 400
        gateway.ingestion.publish_command(device_id, {
            "device_id": device_id,
            "command": command,
            "payload": payload,
        })
        return jsonify({"status": "sent", "device_id": device_id, "command": command})

    return app
