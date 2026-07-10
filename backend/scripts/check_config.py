#!/usr/bin/env python3
"""Quick script to check NT57B08 config from .env file."""
import sys
sys.path.insert(0, '.')
from app.config import settings
print(f"NT57B08_ENABLED={settings.NT57B08_ENABLED}")
print(f"NT57B08_MODULE_COUNT={settings.NT57B08_MODULE_COUNT}")
print(f"NT57B08_PORT={settings.NT57B08_PORT}")
print(f"NT57B08_BAUDRATE={settings.NT57B08_BAUDRATE}")
print(f"NT57B08_SLAVE_ID={settings.NT57B08_SLAVE_ID}")
print(f"NT57B08_FUNCTION_CODE={settings.NT57B08_FUNCTION_CODE}")
