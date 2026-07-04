"""Example usage of the MQTT service.

This script demonstrates how to set callbacks and optionally connect.
It will NOT connect by default to avoid requiring a running broker.
Set environment variable `MQTT_RUN_CONNECT=1` to perform an actual connect.
"""
import os
import time

from app.logger import logger
from app.services.mqtt_service import mqtt_service


def on_connect(client, userdata, flags, rc):
    logger.info(f"example: connected, rc={rc}")
    # subscribe example
    mqtt_service.subscribe("test/topic")


def on_disconnect(client, userdata, rc):
    logger.info(f"example: disconnected, rc={rc}")


def on_message(client, userdata, msg):
    logger.info(f"example: message on {msg.topic}: {msg.payload}")


def main():
    mqtt_service.on_connect_cb = on_connect
    mqtt_service.on_disconnect_cb = on_disconnect
    mqtt_service.on_message_cb = on_message

    run_connect = os.getenv("MQTT_RUN_CONNECT", "0") == "1"
    if run_connect:
        mqtt_service.connect()
        # publish a test message and wait a moment
        mqtt_service.publish("test/topic", "hello from example", qos=0)
        time.sleep(2)
        mqtt_service.disconnect()
    else:
        logger.info("MQTT example loaded; set MQTT_RUN_CONNECT=1 to perform real connect")


if __name__ == "__main__":
    main()
