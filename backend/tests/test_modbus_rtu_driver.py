import inspect
import json
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import pytest

from app.drivers.modbus_rtu.config import load_modbus_rtu_config
from app.drivers.modbus_rtu.driver import ModbusRTUDriver
from app.drivers.modbus_rtu.models import ModbusRTUConfig, RegisterMapping
from app.drivers.modbus_rtu.parser import parse_register_value


class DummyResponse:
    def __init__(self, registers=None, is_error=False, text=""):
        self.registers = registers or []
        self._is_error = is_error
        self._text = text

    def isError(self):
        return self._is_error

    def __str__(self):
        return self._text


class FakeClient:
    def __init__(self, responses=None, connect_ok=True, raise_on_read=None):
        self.responses = list(responses or [])
        self.connect_ok = connect_ok
        self.raise_on_read = raise_on_read
        self.closed = False

    def connect(self):
        return self.connect_ok

    def close(self):
        self.closed = True

    def read_holding_registers(self, *args, **kwargs):
        if self.raise_on_read:
            raise self.raise_on_read
        if self.responses:
            return self.responses.pop(0)
        return None

    def read_input_registers(self, *args, **kwargs):
        return self.read_holding_registers(*args, **kwargs)


class StubMeasurementService:
    def __init__(self):
        self.calls = []

    def save_measurement(self, serial_number, sensor_name, value, timestamp=None):
        self.calls.append((serial_number, sensor_name, value, timestamp))
        return True


class StubDeviceManager:
    def __init__(self):
        self.calls = []

    def ensure_registered(self, device_id, device_data=None, sensor_data_list=None):
        self.calls.append((device_id, device_data or {}, sensor_data_list or []))


@pytest.fixture
def basic_config():
    return ModbusRTUConfig(
        port="COM3",
        baudrate=9600,
        parity="N",
        stopbits=1,
        bytesize=8,
        slave_id=1,
        timeout=0.5,
        poll_interval_seconds=0.1,
        retry_interval_seconds=0.05,
        device_serial="MODBUS-1",
        device_name="Chiller RTU",
        register_mappings=[
            RegisterMapping(
                address=40001,
                register_type="holding",
                sensor_uid="temp_1",
                name="Temperature",
                unit="C",
                scale=0.1,
                offset=0.0,
            )
        ],
    )


def test_driver_initialization(basic_config):
    driver = ModbusRTUDriver(basic_config)
    assert driver.config.port == "COM3"
    assert driver.config.slave_id == 1


def test_register_parsing_scaling_and_offset():
    mapping = RegisterMapping(
        address=10,
        register_type="holding",
        sensor_uid="s1",
        name="Temperature",
        unit="C",
        scale=0.1,
        offset=2.5,
    )
    value = parse_register_value([200], mapping)
    assert value == pytest.approx(22.5)


def test_measurement_forwarding(basic_config):
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[DummyResponse(registers=[187])])

    driver = ModbusRTUDriver(
        basic_config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: fake_client,
    )

    ok = driver.poll_once()
    assert ok
    assert len(ms.calls) == 1
    serial, sensor_uid, value, _ = ms.calls[0]
    assert serial == "MODBUS-1"
    assert sensor_uid == "temp_1"
    assert value == pytest.approx(18.7)


def test_timeout_handling(basic_config):
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[None])

    driver = ModbusRTUDriver(
        basic_config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: fake_client,
    )

    ok = driver.poll_once()
    assert ok
    assert ms.calls == []


def test_reconnect_after_connection_lost(basic_config):
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    first_client = FakeClient(raise_on_read=RuntimeError("connection lost"))
    second_client = FakeClient(responses=[DummyResponse(registers=[250])])
    clients = [first_client, second_client]

    driver = ModbusRTUDriver(
        basic_config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: clients.pop(0),
    )

    ok1 = driver.poll_once()
    ok2 = driver.poll_once()

    assert ok1
    assert ok2
    assert len(ms.calls) == 1
    assert ms.calls[0][2] == pytest.approx(25.0)


def test_automatic_device_registration(basic_config):
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[DummyResponse(registers=[100])])

    driver = ModbusRTUDriver(
        basic_config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: fake_client,
    )

    driver.poll_once()
    assert len(dm.calls) == 1
    device_id, _, sensors = dm.calls[0]
    assert device_id == "MODBUS-1"
    assert len(sensors) == 1
    assert sensors[0]["sensor_id"] == "temp_1"


def test_config_loader_from_settings(monkeypatch):
    monkeypatch.setattr("app.drivers.modbus_rtu.config.settings.MODBUS_RTU_PORT", "COM9")
    monkeypatch.setattr("app.drivers.modbus_rtu.config.settings.MODBUS_RTU_BAUDRATE", 19200)
    monkeypatch.setattr("app.drivers.modbus_rtu.config.settings.MODBUS_RTU_PARITY", "E")
    monkeypatch.setattr("app.drivers.modbus_rtu.config.settings.MODBUS_RTU_STOPBITS", 2)
    monkeypatch.setattr("app.drivers.modbus_rtu.config.settings.MODBUS_RTU_BYTESIZE", 8)
    monkeypatch.setattr("app.drivers.modbus_rtu.config.settings.MODBUS_RTU_SLAVE_ID", 7)
    monkeypatch.setattr("app.drivers.modbus_rtu.config.settings.MODBUS_RTU_TIMEOUT", 1.5)
    monkeypatch.setattr("app.drivers.modbus_rtu.config.settings.MODBUS_RTU_POLL_INTERVAL", 2.0)
    monkeypatch.setattr("app.drivers.modbus_rtu.config.settings.MODBUS_RTU_RETRY_INTERVAL", 0.5)
    monkeypatch.setattr("app.drivers.modbus_rtu.config.settings.MODBUS_RTU_DEVICE_SERIAL", "MODBUS-A")
    monkeypatch.setattr("app.drivers.modbus_rtu.config.settings.MODBUS_RTU_DEVICE_NAME", "RTU A")
    monkeypatch.setattr(
        "app.drivers.modbus_rtu.config.settings.MODBUS_RTU_REGISTER_MAP",
        json.dumps(
            [
                {
                    "address": 40001,
                    "register_type": "holding",
                    "sensor_uid": "temp",
                    "name": "Temperature",
                    "unit": "C",
                    "scale": 0.1,
                    "offset": 0,
                }
            ]
        ),
    )

    cfg = load_modbus_rtu_config()
    assert cfg.port == "COM9"
    assert cfg.baudrate == 19200
    assert len(cfg.register_mappings) == 1
    assert cfg.register_mappings[0].sensor_uid == "temp"


def test_no_direct_database_writes_in_driver():
    src = inspect.getsource(sys.modules["app.drivers.modbus_rtu.driver"])
    assert "SessionLocal" not in src
    assert "sqlalchemy" not in src.lower()
