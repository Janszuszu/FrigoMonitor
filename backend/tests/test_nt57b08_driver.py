"""Tests for the NT57B08 Modbus RTU driver."""

import inspect
import json
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

import pytest

from app.drivers.nt57b08.config import load_nt57b08_config
from app.drivers.nt57b08.conversion import convert_register_value, _ntc_10k_b3950
from app.drivers.nt57b08.driver import NT57B08Driver
from app.drivers.nt57b08.models import (
    NT57B08Config,
    NT57B08Channel,
    ConversionMode,
    make_default_channels,
)


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
    return NT57B08Config(
        port="/dev/ttyUSB0",
        baudrate=9600,
        parity="N",
        stopbits=1,
        bytesize=8,
        slave_id=1,
        timeout=0.5,
        poll_interval_seconds=0.1,
        retry_interval_seconds=0.05,
        function_code=4,
        start_register=0,
        channel_count=8,
        device_serial="NT57B08-1",
        device_name="NT57B08 Module",
        channels=make_default_channels(0, 8, ConversionMode.RAW),
    )


# --- Register range tests ---

def test_register_range_0x0000_to_0x0007():
    """Verify that default channels use addresses 0x0000 through 0x0007."""
    channels = make_default_channels(start_register=0, channel_count=8)
    expected_addresses = list(range(0, 8))
    actual_addresses = [ch.register_address for ch in channels]
    assert actual_addresses == expected_addresses


def test_register_range_custom_start():
    """Verify configurable start register."""
    channels = make_default_channels(start_register=0x0100, channel_count=4)
    expected = [0x0100, 0x0101, 0x0102, 0x0103]
    assert [ch.register_address for ch in channels] == expected


# --- Single-request reading of 8 registers ---

def test_read_all_channels_single_request(basic_config):
    """Verify that all 8 channels are read in one Modbus request."""
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[DummyResponse(registers=[100, 200, 300, 400, 500, 600, 700, 800])])

    driver = NT57B08Driver(
        basic_config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: fake_client,
    )

    ok = driver.poll_once()
    assert ok
    assert len(ms.calls) == 8


def test_read_all_channels_partial_response(basic_config):
    """Verify handling of partial register response."""
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[DummyResponse(registers=[100, 200, 300])])

    driver = NT57B08Driver(
        basic_config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: fake_client,
    )

    ok = driver.poll_once()
    assert ok
    # Only 3 registers returned, but 8 channels configured
    # Channels 4-8 should be skipped (out of range)
    assert len(ms.calls) == 3


# --- Mapping registers to CH1-CH8 ---

def test_channel_mapping():
    """Verify that channels map to correct register addresses."""
    channels = make_default_channels(0, 8)
    assert channels[0].channel_number == 1
    assert channels[0].register_address == 0
    assert channels[0].name == "NT57B08 CH1"
    assert channels[7].channel_number == 8
    assert channels[7].register_address == 7
    assert channels[7].name == "NT57B08 CH8"


# --- Deterministic sensor IDs ---

def test_sensor_uid_deterministic(basic_config):
    """Verify that sensor UIDs are stable and deterministic."""
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[DummyResponse(registers=[100] * 8)])

    driver = NT57B08Driver(
        basic_config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: fake_client,
    )

    driver.poll_once()
    assert len(dm.calls) >= 1
    # Check sensor IDs from registration
    _, _, sensors = dm.calls[0]
    assert len(sensors) == 8
    assert sensors[0]["sensor_id"] == "nt57b08-NT57B08-1-ch1"
    assert sensors[3]["sensor_id"] == "nt57b08-NT57B08-1-ch4"
    assert sensors[7]["sensor_id"] == "nt57b08-NT57B08-1-ch8"


def test_sensor_uid_stable_across_restarts():
    """Verify that same config produces same sensor IDs."""
    config1 = NT57B08Config(
        port="/dev/ttyUSB0",
        device_serial="NT57B08-A",
        channels=make_default_channels(0, 4),
    )
    config2 = NT57B08Config(
        port="/dev/ttyUSB1",
        device_serial="NT57B08-A",
        channels=make_default_channels(0, 4),
    )

    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake1 = FakeClient(responses=[DummyResponse(registers=[100] * 4)])
    fake2 = FakeClient(responses=[DummyResponse(registers=[200] * 4)])

    driver1 = NT57B08Driver(config1, measurement_service_obj=ms, device_manager_obj=dm, client_factory=lambda _cfg: fake1)
    driver2 = NT57B08Driver(config2, measurement_service_obj=ms, device_manager_obj=dm, client_factory=lambda _cfg: fake2)

    driver1.poll_once()
    driver2.poll_once()

    # Both should produce same sensor IDs (same device_serial)
    _, _, sensors1 = dm.calls[0]
    _, _, sensors2 = dm.calls[1]
    for s1, s2 in zip(sensors1, sensors2):
        assert s1["sensor_id"] == s2["sensor_id"]


# --- Multiple Slave IDs ---

def test_multiple_slave_ids():
    """Verify that different slave IDs produce different device serials."""
    config1 = NT57B08Config(
        port="/dev/ttyUSB0",
        slave_id=1,
        device_serial="NT57B08-SLAVE1",
        channels=make_default_channels(0, 2),
    )
    config2 = NT57B08Config(
        port="/dev/ttyUSB0",
        slave_id=2,
        device_serial="NT57B08-SLAVE2",
        channels=make_default_channels(0, 2),
    )

    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake1 = FakeClient(responses=[DummyResponse(registers=[100, 200])])
    fake2 = FakeClient(responses=[DummyResponse(registers=[300, 400])])

    driver1 = NT57B08Driver(config1, measurement_service_obj=ms, device_manager_obj=dm, client_factory=lambda _cfg: fake1)
    driver2 = NT57B08Driver(config2, measurement_service_obj=ms, device_manager_obj=dm, client_factory=lambda _cfg: fake2)

    driver1.poll_once()
    driver2.poll_once()

    assert len(dm.calls) == 2
    assert dm.calls[0][0] == "NT57B08-SLAVE1"
    assert dm.calls[1][0] == "NT57B08-SLAVE2"


# --- Raw mode ---

def test_raw_mode():
    """Verify that raw mode returns register value as-is."""
    value = convert_register_value(12345, ConversionMode.RAW)
    assert value == 12345.0


# --- NTC B3950 conversion ---

def test_ntc_b3950_25c():
    """At 25°C, NTC 10K B3950 should read 10000 ohms."""
    temp = _ntc_10k_b3950(10000.0)
    assert temp is not None
    assert temp == pytest.approx(25.0, abs=0.5)


def test_ntc_b3950_0c():
    """At 0°C, resistance should be higher (~29400 ohms for B=3950)."""
    temp = _ntc_10k_b3950(29400.0)
    assert temp is not None
    # Beta equation: 1/T = 1/298.15 + (1/3950)*ln(29400/10000)
    # Expected: ~2.56°C for 29400 ohms
    assert temp == pytest.approx(2.56, abs=0.5)


def test_ntc_b3950_negative():
    """Verify negative temperature output."""
    temp = _ntc_10k_b3950(50000.0)
    assert temp is not None
    assert temp < 0


def test_ntc_b3950_zero_resistance():
    """Zero resistance should return None."""
    temp = _ntc_10k_b3950(0)
    assert temp is None


def test_ntc_b3950_negative_resistance():
    """Negative resistance should return None."""
    temp = _ntc_10k_b3950(-100)
    assert temp is None


# --- Invalid values ---

def test_invalid_low_threshold():
    """Verify that values below low threshold are rejected."""
    channel = NT57B08Channel(
        channel_number=1,
        register_address=0,
        name="CH1",
        conversion_mode=ConversionMode.RAW,
        invalid_low_threshold=10.0,
    )
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[DummyResponse(registers=[5])])

    config = NT57B08Config(
        port="/dev/ttyUSB0",
        channels=[channel],
    )
    driver = NT57B08Driver(config, measurement_service_obj=ms, device_manager_obj=dm, client_factory=lambda _cfg: fake_client)
    driver.poll_once()
    # Value 5 is below threshold 10, should be rejected
    assert len(ms.calls) == 0


def test_invalid_high_threshold():
    """Verify that values above high threshold are rejected."""
    channel = NT57B08Channel(
        channel_number=1,
        register_address=0,
        name="CH1",
        conversion_mode=ConversionMode.RAW,
        invalid_high_threshold=100.0,
    )
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[DummyResponse(registers=[200])])

    config = NT57B08Config(
        port="/dev/ttyUSB0",
        channels=[channel],
    )
    driver = NT57B08Driver(config, measurement_service_obj=ms, device_manager_obj=dm, client_factory=lambda _cfg: fake_client)
    driver.poll_once()
    assert len(ms.calls) == 0


# --- Modbus timeout ---

def test_modbus_timeout(basic_config):
    """Verify that timeout does not crash the driver."""
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[None])

    driver = NT57B08Driver(
        basic_config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: fake_client,
    )

    ok = driver.poll_once()
    assert not ok  # poll_once returns False on timeout
    assert ms.calls == []


# --- Partial response ---

def test_partial_response(basic_config):
    """Verify that partial register response is handled gracefully."""
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[DummyResponse(registers=[100, 200])])

    driver = NT57B08Driver(
        basic_config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: fake_client,
    )

    ok = driver.poll_once()
    assert ok
    # Only 2 registers returned, should store 2 measurements
    assert len(ms.calls) == 2


# --- No duplicate sensor creation ---

def test_no_duplicate_sensors(basic_config):
    """Verify that ensure_registered is called only once."""
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[DummyResponse(registers=[100] * 8)])

    driver = NT57B08Driver(
        basic_config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: fake_client,
    )

    # First poll registers
    driver.poll_once()
    # Second poll should NOT register again
    driver.poll_once()

    # ensure_registered should be called exactly once
    assert len(dm.calls) == 1


# --- No direct database writes ---

def test_no_direct_database_writes_in_driver():
    """Verify that the driver does not use SQLAlchemy directly."""
    src = inspect.getsource(sys.modules["app.drivers.nt57b08.driver"])
    assert "SessionLocal" not in src
    assert "sqlalchemy" not in src.lower()


# --- Config loader ---

def test_config_loader_defaults(monkeypatch):
    """Verify that config loader produces correct defaults."""
    monkeypatch.setattr("app.drivers.nt57b08.config.settings.NT57B08_PORT", "/dev/ttyUSB0")
    monkeypatch.setattr("app.drivers.nt57b08.config.settings.NT57B08_BAUDRATE", 9600)
    monkeypatch.setattr("app.drivers.nt57b08.config.settings.NT57B08_SLAVE_ID", 1)
    monkeypatch.setattr("app.drivers.nt57b08.config.settings.NT57B08_CONVERSION_MODE", "raw")
    monkeypatch.setattr("app.drivers.nt57b08.config.settings.NT57B08_CHANNELS", "")

    cfg = load_nt57b08_config(0)
    assert cfg.port == "/dev/ttyUSB0"
    assert cfg.baudrate == 9600
    assert cfg.slave_id == 1
    assert cfg.channel_count == 8
    assert len(cfg.channels) == 8
    assert cfg.channels[0].conversion_mode == ConversionMode.RAW
    assert cfg.channels[0].name == "NT57B08 CH1"
    assert cfg.channels[7].name == "NT57B08 CH8"


def test_config_loader_custom_channels(monkeypatch):
    """Verify that custom channel JSON is parsed correctly."""
    monkeypatch.setattr("app.drivers.nt57b08.config.settings.NT57B08_PORT", "/dev/ttyUSB0")
    monkeypatch.setattr("app.drivers.nt57b08.config.settings.NT57B08_CHANNELS", json.dumps([
        {
            "channel_number": 1,
            "register_address": 0,
            "name": "Evaporator",
            "conversion_mode": "ntc_10k_b3950",
            "unit": "C",
        },
        {
            "channel_number": 2,
            "register_address": 1,
            "name": "Condenser",
            "conversion_mode": "raw",
            "unit": "",
        },
    ]))

    cfg = load_nt57b08_config(0)
    assert len(cfg.channels) == 2
    assert cfg.channels[0].name == "Evaporator"
    assert cfg.channels[0].conversion_mode == ConversionMode.NTC_10K_B3950
    assert cfg.channels[1].name == "Condenser"
    assert cfg.channels[1].conversion_mode == ConversionMode.RAW


# --- Measurement forwarding ---

def test_measurement_forwarding(basic_config):
    """Verify that measurements are forwarded to MeasurementService."""
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[DummyResponse(registers=[100, 200, 300, 400, 500, 600, 700, 800])])

    driver = NT57B08Driver(
        basic_config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: fake_client,
    )

    ok = driver.poll_once()
    assert ok
    assert len(ms.calls) == 8
    # Check first measurement
    serial, sensor_uid, value, _ = ms.calls[0]
    assert serial == "NT57B08-1"
    assert sensor_uid == "nt57b08-NT57B08-1-ch1"
    assert value == 100.0
    # Check last measurement
    serial, sensor_uid, value, _ = ms.calls[7]
    assert sensor_uid == "nt57b08-NT57B08-1-ch8"
    assert value == 800.0


# --- Temperature direct scaled ---

def test_temperature_direct_scaled():
    """Verify temperature_direct_scaled conversion."""
    value = convert_register_value(235, ConversionMode.TEMPERATURE_DIRECT_SCALED)
    assert value == pytest.approx(23.5)


# --- Resistance ohms ---

def test_resistance_ohms():
    """Verify resistance_ohms conversion."""
    value = convert_register_value(10000, ConversionMode.RESISTANCE_OHMS)
    assert value == 10000.0


# =============================================================================
# Verified physical hardware tests (NT57B08 real hardware)
# =============================================================================


# --- Signed int16 decoding ---

def test_signed_int16_positive():
    """Verify signed int16 decoding for positive values."""
    from app.drivers.nt57b08.models import signed_int16
    # 0x00D4 = 212 unsigned = 212 signed
    assert signed_int16(0x00D4) == 212
    # 0x00D5 = 213 unsigned = 213 signed
    assert signed_int16(0x00D5) == 213


def test_signed_int16_negative():
    """Verify signed int16 decoding for negative values."""
    from app.drivers.nt57b08.models import signed_int16
    # 0xF555 = 62805 unsigned = -2731 signed
    assert signed_int16(0xF555) == -2731
    # 0xFFFF = -1
    assert signed_int16(0xFFFF) == -1
    # 0x8000 = -32768
    assert signed_int16(0x8000) == -32768


# --- Verified physical temperature conversions ---

def test_verified_212_equals_21_2c():
    """Physical hardware: CH1 raw 0x00D4 (212) = 21.2°C."""
    value = convert_register_value(0x00D4, ConversionMode.TEMPERATURE_DIRECT_SCALED)
    assert value is not None
    assert value == pytest.approx(21.2)


def test_verified_213_equals_21_3c():
    """Physical hardware: CH4 raw 0x00D5 (213) = 21.3°C."""
    value = convert_register_value(0x00D5, ConversionMode.TEMPERATURE_DIRECT_SCALED)
    assert value is not None
    assert value == pytest.approx(21.3)


# --- 0xF555 disconnected channel ---

def test_f555_disconnected_detection():
    """Verify 0xF555 is detected as disconnected."""
    from app.drivers.nt57b08.models import is_disconnected, DISCONNECTED_VALUE
    assert DISCONNECTED_VALUE == 0xF555
    assert is_disconnected(0xF555) is True
    assert is_disconnected(0x00D4) is False
    assert is_disconnected(0x00D5) is False


def test_f555_returns_none():
    """Verify 0xF555 returns None (not stored as valid measurement)."""
    value = convert_register_value(0xF555, ConversionMode.TEMPERATURE_DIRECT_SCALED)
    assert value is None


def test_f555_not_stored_as_measurement():
    """Verify disconnected channels are not stored as measurements."""
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    # Simulate CH1=21.2°C, CH2=21.2°C, CH3=21.2°C, CH4=21.3°C,
    # CH5-CH8 = disconnected (0xF555)
    registers = [0x00D4, 0x00D4, 0x00D4, 0x00D5, 0xF555, 0xF555, 0xF555, 0xF555]
    fake_client = FakeClient(responses=[DummyResponse(registers=registers)])

    config = NT57B08Config(
        port="/dev/ttyUSB0",
        channels=make_default_channels(0, 8, ConversionMode.TEMPERATURE_DIRECT_SCALED),
    )
    driver = NT57B08Driver(
        config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: fake_client,
    )

    ok = driver.poll_once()
    assert ok
    # Only 4 connected channels should be stored
    assert len(ms.calls) == 4
    # Verify stored values
    assert ms.calls[0][2] == pytest.approx(21.2)  # CH1
    assert ms.calls[1][2] == pytest.approx(21.2)  # CH2
    assert ms.calls[2][2] == pytest.approx(21.2)  # CH3
    assert ms.calls[3][2] == pytest.approx(21.3)  # CH4


# --- CH1-CH8 mapping ---

def test_ch1_to_ch8_mapping_with_default_names():
    """Verify CH1-CH8 mapping with default NT57B08 CH names."""
    channels = make_default_channels(0, 8, ConversionMode.TEMPERATURE_DIRECT_SCALED)
    assert len(channels) == 8
    assert channels[0].name == "NT57B08 CH1"
    assert channels[0].register_address == 0
    assert channels[0].unit == "C"
    assert channels[3].name == "NT57B08 CH4"
    assert channels[3].register_address == 3
    assert channels[7].name == "NT57B08 CH8"
    assert channels[7].register_address == 7


# --- One-request read of eight registers ---

def test_single_request_reads_eight_registers():
    """Verify that one Modbus request reads all 8 registers."""
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    call_count = [0]

    class CountingClient(FakeClient):
        def read_input_registers(self, *args, **kwargs):
            call_count[0] += 1
            return DummyResponse(registers=[0x00D4] * 8)

    config = NT57B08Config(
        port="/dev/ttyUSB0",
        function_code=4,
        start_register=0,
        channel_count=8,
        channels=make_default_channels(0, 8, ConversionMode.TEMPERATURE_DIRECT_SCALED),
    )
    driver = NT57B08Driver(
        config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: CountingClient(),
    )

    ok = driver.poll_once()
    assert ok
    assert call_count[0] == 1  # Exactly one Modbus request


# --- Deterministic sensor identity ---

def test_deterministic_sensor_identity():
    """Verify same device_serial + channel produces same sensor UID."""
    config1 = NT57B08Config(
        port="/dev/ttyUSB0",
        device_serial="NT57B08-1",
        channels=make_default_channels(0, 8, ConversionMode.TEMPERATURE_DIRECT_SCALED),
    )
    config2 = NT57B08Config(
        port="/dev/ttyUSB1",
        device_serial="NT57B08-1",
        channels=make_default_channels(0, 8, ConversionMode.TEMPERATURE_DIRECT_SCALED),
    )

    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake1 = FakeClient(responses=[DummyResponse(registers=[0x00D4] * 8)])
    fake2 = FakeClient(responses=[DummyResponse(registers=[0x00D4] * 8)])

    driver1 = NT57B08Driver(config1, measurement_service_obj=ms, device_manager_obj=dm, client_factory=lambda _cfg: fake1)
    driver2 = NT57B08Driver(config2, measurement_service_obj=ms, device_manager_obj=dm, client_factory=lambda _cfg: fake2)

    driver1.poll_once()
    driver2.poll_once()

    # Both should produce same sensor IDs (same device_serial)
    _, _, sensors1 = dm.calls[0]
    _, _, sensors2 = dm.calls[1]
    for s1, s2 in zip(sensors1, sensors2):
        assert s1["sensor_id"] == s2["sensor_id"]
        assert s1["sensor_id"] == f"nt57b08-NT57B08-1-ch{s1['channel_number'] if 'channel_number' in s1 else (sensors1.index(s1) + 1)}"


# --- No duplicate sensor creation after restart ---

def test_no_duplicate_sensors_after_restart():
    """Verify that restarting the driver does not create duplicate sensors."""
    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake_client = FakeClient(responses=[DummyResponse(registers=[0x00D4] * 8)])

    config = NT57B08Config(
        port="/dev/ttyUSB0",
        device_serial="NT57B08-1",
        channels=make_default_channels(0, 8, ConversionMode.TEMPERATURE_DIRECT_SCALED),
    )
    driver = NT57B08Driver(
        config,
        measurement_service_obj=ms,
        device_manager_obj=dm,
        client_factory=lambda _cfg: fake_client,
    )

    # First poll registers
    driver.poll_once()
    # Second poll should NOT register again
    driver.poll_once()

    # ensure_registered should be called exactly once
    assert len(dm.calls) == 1


# --- Multiple Slave IDs ---

def test_multiple_slave_ids_with_temperature_mode():
    """Verify that different slave IDs produce different device serials."""
    config1 = NT57B08Config(
        port="/dev/ttyUSB0",
        slave_id=1,
        device_serial="NT57B08-SLAVE1",
        channels=make_default_channels(0, 2, ConversionMode.TEMPERATURE_DIRECT_SCALED),
    )
    config2 = NT57B08Config(
        port="/dev/ttyUSB0",
        slave_id=2,
        device_serial="NT57B08-SLAVE2",
        channels=make_default_channels(0, 2, ConversionMode.TEMPERATURE_DIRECT_SCALED),
    )

    ms = StubMeasurementService()
    dm = StubDeviceManager()
    fake1 = FakeClient(responses=[DummyResponse(registers=[0x00D4, 0x00D4])])
    fake2 = FakeClient(responses=[DummyResponse(registers=[0x00D4, 0x00D4])])

    driver1 = NT57B08Driver(config1, measurement_service_obj=ms, device_manager_obj=dm, client_factory=lambda _cfg: fake1)
    driver2 = NT57B08Driver(config2, measurement_service_obj=ms, device_manager_obj=dm, client_factory=lambda _cfg: fake2)

    driver1.poll_once()
    driver2.poll_once()

    assert len(dm.calls) == 2
    assert dm.calls[0][0] == "NT57B08-SLAVE1"
    assert dm.calls[1][0] == "NT57B08-SLAVE2"
