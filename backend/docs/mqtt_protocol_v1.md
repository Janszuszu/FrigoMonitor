# FrigoMonitor MQTT Protocol v1.0

Version: 1.0

Overview
--------
This document specifies the MQTT topic layout, JSON payload formats, QoS recommendations, retained message policies, Last Will behavior, and rules for online/offline and duplicate handling for FrigoMonitor devices.

Topics
------
Base topic prefix: `frigomonitor`

Topics (use {serial} substitution):

- `frigomonitor/device/{serial}/status`  — retained; device online/offline status
- `frigomonitor/device/{serial}/heartbeat` — periodic heartbeat (transient)
- `frigomonitor/device/{serial}/measurement` — measurements from device (sensor readings)
- `frigomonitor/device/{serial}/alarm` — alarm events raised by device
- `frigomonitor/device/{serial}/config` — device configuration updates (server -> device)

Topic details
-------------
- `status`
  - Purpose: indicate that a device is online/offline.
  - Retained: recommended `yes` — broker keeps last known device status.
  - QoS: 1 (at least once) recommended for status updates.
  - Payload: see `Heartbeat` format (subset) or simple status object.

- `heartbeat`
  - Purpose: periodic health ping from device.
  - Retained: `no`.
  - QoS: 0 or 1; prefer 0 for high-volume, 1 for reliability.

- `measurement`
  - Purpose: deliver sensor measurements.
  - Retained: `no` (measurements are time series; do not retain by default).
  - QoS: recommended 1 (at least once) — consumer should deduplicate.

- `alarm`
  - Purpose: notify server of alarm events.
  - Retained: optional; default `no`.
  - QoS: 1 recommended.

- `config`
  - Purpose: server -> device configuration messages.
  - Retained: `yes` (retain last config so new devices get it on subscription).
  - QoS: 1 recommended.

Last Will and Testament
-----------------------
- Last Will topic: `frigomonitor/device/{serial}/status`
- Last Will payload (JSON): {"protocol_version":"1.0","timestamp":"<ISO8601 UTC>","serial_number":"<serial>","status":"offline","message_id":"<id>"}
- Last Will QoS: 1
- Last Will retain: true (so offline status persists until device returns online)

Payload common fields
---------------------
All payloads MUST include these fields unless noted otherwise:

- `protocol_version` (string) — e.g. `"1.0"`
- `timestamp` (string, ISO8601 UTC) — when message was produced by device
- `serial_number` (string)
- `message_id` (string) — unique id for message (UUID recommended)

Heartbeat payload (example)
---------------------------
{
  "protocol_version": "1.0",
  "timestamp": "2026-07-04T12:34:56Z",
  "serial_number": "DEV123",
  "message_id": "uuid-...",
  "status": "online",
  "uptime_seconds": 12345,
  "firmware": "1.2.3"
}

Measurement payload (example)
----------------------------
{
  "protocol_version": "1.0",
  "timestamp": "2026-07-04T12:35:00Z",
  "serial_number": "DEV123",
  "message_id": "uuid-...",
  "sensor_id": "temp_sensor_1",
  "measured_at": "2026-07-04T12:34:59Z",
  "value": 12.34,
  "unit": "C"
}

Alarm payload (example)
-----------------------
{
  "protocol_version": "1.0",
  "timestamp": "2026-07-04T12:35:10Z",
  "serial_number": "DEV123",
  "message_id": "uuid-...",
  "sensor_id": "temp_sensor_1",
  "alarm_type": "threshold_exceeded",
  "severity": "critical",
  "details": "value=100.1"
}

Device registration (example)
----------------------------
Devices can announce themselves via `measurement` or a dedicated registration message on `status`.
Example registration payload:

{
  "protocol_version": "1.0",
  "timestamp": "2026-07-04T12:35:30Z",
  "serial_number": "DEV123",
  "message_id": "uuid-...",
  "device_name": "Fridge A1",
  "sensors": [
    {"sensor_id":"temp_sensor_1","name":"Temp 1","type":"temperature"}
  ]
}

Configuration payload (server -> device)
----------------------------------------
{
  "protocol_version": "1.0",
  "timestamp": "2026-07-04T12:36:00Z",
  "serial_number": "DEV123",
  "message_id": "uuid-...",
  "config": {
    "reporting_interval_seconds": 60,
    "thresholds": {"temp_sensor_1": {"min": -10, "max": 10}}
  }
}

Duplicate message handling
--------------------------
- Receivers MUST apply idempotency based on `message_id` and `measured_at` (for measurements).
- Store a short-lived cache of recent `message_id`s to drop duplicates.

Online/offline rules
--------------------
- Devices SHOULD publish a retained `status` message with `status":"online"` on connect.
- On graceful disconnect, publish `status":"offline"` retained (or broker LWT will handle it).

QoS recommendations summary
--------------------------
- `status` : QoS 1, retained true
- `heartbeat`: QoS 0 or 1, retained false
- `measurement`: QoS 1, retained false
- `alarm`: QoS 1, retained false
- `config`: QoS 1, retained true

Notes
-----
- Timestamp fields should be ISO8601 UTC. Use timezone-aware datetimes.
- This protocol is intentionally conservative: do not retain measurement payloads.
