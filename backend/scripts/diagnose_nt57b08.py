#!/usr/bin/env python3
"""
NT57B08 Modbus RTU Diagnostic Script
Connects to the physical NT57B08 via FTDI FT232R USB-to-RS485 converter.
Reads 8 input registers (function code 04) starting at 0x0000.

Usage:
    python scripts/diagnose_nt57b08.py

This script performs a READ-ONLY test. No Modbus registers are written.
"""

import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException


def main():
    print("=" * 60)
    print("NT57B08 Modbus RTU Diagnostic")
    print("=" * 60)

    # Use the stable FTDI serial device path (by serial number A50285BI)
    port = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A50285BI-if00-port0"

    config = {
        "port": port,
        "baudrate": 9600,
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1,
        "timeout": 2.0,
    }

    print("\nConfiguration:")
    print(f"  Port:       {config['port']}")
    print("  Slave ID:   1")
    print(f"  Baud rate:  {config['baudrate']}")
    print(f"  Data bits:  {config['bytesize']}")
    print(f"  Parity:     {config['parity']}")
    print(f"  Stop bits:  {config['stopbits']}")
    print(f"  Timeout:    {config['timeout']}s")
    print("  Function:   04 (Read Input Registers)")
    print("  Start addr: 0x0000")
    print("  Quantity:   8 registers")
    print()

    # Create Modbus client directly for diagnostic purposes
    client = ModbusSerialClient(
        port=config["port"],
        baudrate=config["baudrate"],
        bytesize=config["bytesize"],
        parity=config["parity"],
        stopbits=config["stopbits"],
        timeout=config["timeout"],
    )

    try:
        print("Opening serial port...")
        connected = client.connect()
        if not connected:
            print("ERROR: Failed to connect to serial port.", file=sys.stderr)
            sys.exit(1)
        print("Serial port opened successfully.")
        print()

        # Small delay to let the device settle
        time.sleep(0.2)

        print("Sending Modbus RTU request: Function 04, Read Input Registers")
        print("  Request: slave=1, func=0x04, addr=0x0000, count=8")
        print()

        # Try function code 04 (Read Input Registers)
        response = client.read_input_registers(
            address=0x0000,
            count=8,
            slave=1,
        )

        # Check for Modbus errors
        if response is None:
            print("ERROR: No response received (timeout).", file=sys.stderr)
            print()
            print("Possible causes:")
            print("  - Wrong slave ID (trying 1)")
            print("  - Wrong baud rate (trying 9600)")
            print("  - Wiring issue (A/B reversed?)")
            print("  - RS485 converter not powered")
            print("  - Termination resistor missing")
            sys.exit(1)

        if hasattr(response, "isError") and response.isError():
            error_msg = str(response)
            print(f"ERROR: Modbus exception response: {error_msg}", file=sys.stderr)
            print()
            print("Diagnosing error...")
            lower = error_msg.lower()
            if "crc" in lower:
                print("  -> CRC error: possible baud rate mismatch or wiring noise")
            elif "timeout" in lower:
                print("  -> Timeout: device not responding")
            elif "illegal function" in lower:
                print("  -> Function 04 not supported. Try function 03 (holding registers)")
            elif "illegal data address" in lower:
                print("  -> Invalid register address")
            elif "illegal data value" in lower:
                print("  -> Invalid data value in request")
            elif "gateway" in lower or "path" in lower:
                print("  -> Gateway/Path error")
            else:
                print(f"  -> Unknown error: {error_msg}")
            sys.exit(1)

        # Extract registers
        registers = getattr(response, "registers", None)
        if not registers:
            print("ERROR: Empty register response.", file=sys.stderr)
            sys.exit(1)

        print("=" * 60)
        print("RAW REGISTER VALUES FROM PHYSICAL NT57B08")
        print("=" * 60)
        print()

        channel_names = ["CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8"]

        for i, (name, value) in enumerate(zip(channel_names, registers)):
            # Show as signed 16-bit if applicable
            if value & 0x8000:
                signed_val = value - 0x10000
            else:
                signed_val = value

            # Interpret as two bytes
            high_byte = (value >> 8) & 0xFF
            low_byte = value & 0xFF

            print(f"  {name} | 0x{i:04X} | raw: 0x{value:04X} | "
                  f"unsigned: {value:5d} | signed: {signed_val:5d} | "
                  f"bytes: [{high_byte:3d}, {low_byte:3d}]")

        print()
        print(f"Total registers read: {len(registers)}")
        print()
        print("=" * 60)
        print("Diagnostic complete. No registers were written.")
        print("=" * 60)

    except ModbusException as e:
        print(f"\nModbusException: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        print(f"Error type: {type(e).__name__}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            client.close()
            print("\nSerial port closed.")
        except Exception:
            pass


if __name__ == "__main__":
    main()
