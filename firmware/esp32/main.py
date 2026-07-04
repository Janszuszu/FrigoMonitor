"""Main entrypoint for WiFi manager sprint."""

import time

import config
from constants import MAIN_LOOP_SLEEP_MS
from logger import error, info, set_debug, warning
from mqtt_client import MQTTManager
from sensor_manager import SensorManager
from system_info import SystemInfo
from version import DEVICE_TYPE, VERSION
from wifi import WiFiConnectionTimeoutError, WiFiManager


def initialize_logger() -> None:
    """Initialize logger configuration."""
    set_debug(config.DEBUG_ENABLED)
    info("Logger initialized")


def initialize_wifi() -> WiFiManager:
    """Initialize and connect WiFi module."""
    timeout_s = int(getattr(config, "WIFI_CONNECT_TIMEOUT_S", 20))
    wifi = WiFiManager(
        config.WIFI_SSID,
        config.WIFI_PASSWORD,
        timeout_s=timeout_s,
    )
    wifi.connect()
    return wifi


def initialize_mqtt() -> MQTTManager:
    """Initialize and connect MQTT manager."""
    mqtt = MQTTManager(
        host=config.MQTT_HOST,
        port=config.MQTT_PORT,
        username=config.MQTT_USER,
        password=config.MQTT_PASSWORD,
        client_id=config.DEVICE_ID,
        keepalive=config.MQTT_KEEPALIVE,
    )

    if not mqtt.connect():
        raise RuntimeError("MQTT connect failed")

    return mqtt


def initialize_sensors() -> SensorManager:
    """Initialize sensor manager and discover DS18B20 sensors."""
    sensors = SensorManager()
    return sensors


def print_sensor_readings(measurements: list) -> None:
    """Log sensor count and latest readings."""
    info("Sensor count: %s" % len(measurements))
    for item in measurements:
        info("ROM: %s" % item.get("rom"))
        info("Temperature: %s" % item.get("temperature"))


def print_runtime_info(system_info: SystemInfo) -> None:
    """Print required startup runtime details."""
    snapshot = system_info.snapshot()
    board = system_info.get_board_name()
    info("Firmware version: %s" % VERSION)
    info("Board: %s" % (board if board is not None else DEVICE_TYPE))
    info("IP: %s" % snapshot.get("ip"))
    info("RSSI: %s" % snapshot.get("rssi"))
    info("MAC: %s" % snapshot.get("mac"))


def publish_measurement_cycle(mqtt: MQTTManager, sensors: SensorManager) -> None:
    """Read and publish one measurement batch."""
    measurements = sensors.read_all()
    if not measurements:
        warning("Measurement skipped")
        return

    if not mqtt.publish_measurements(measurements):
        warning("Measurement skipped")


def idle_loop(mqtt: MQTTManager, sensors: SensorManager) -> None:
    """Minimal idle loop to keep firmware running."""
    measurement_interval_ms = 30000
    start = time.ticks_ms()

    info("Main loop started")
    while True:
        mqtt.check_messages()

        if time.ticks_diff(time.ticks_ms(), start) >= measurement_interval_ms:
            publish_measurement_cycle(mqtt, sensors)
            start = time.ticks_ms()

        time.sleep_ms(MAIN_LOOP_SLEEP_MS)


def main() -> None:
    """Run WiFi manager startup sequence."""
    initialize_logger()
    info("Starting firmware %s on %s" % (VERSION, DEVICE_TYPE))

    try:
        wifi = initialize_wifi()
    except WiFiConnectionTimeoutError as exc:
        error(str(exc))
        raise

    mqtt = initialize_mqtt()
    mqtt.publish_online()
    mqtt.publish_heartbeat()

    sensors = initialize_sensors()
    discovered = sensors.discover()

    mqtt.publish_device_registration()
    for sensor in discovered:
        mqtt.publish_sensor_registration(sensor.get("rom"))

    first_measurements = sensors.read_all()
    print_sensor_readings(first_measurements)
    if not mqtt.publish_measurements(first_measurements):
        warning("Measurement skipped")

    _ = wifi
    print_runtime_info(SystemInfo())
    idle_loop(mqtt, sensors)


if __name__ == "__main__":
    main()
