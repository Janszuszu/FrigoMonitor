from fastapi import APIRouter

from . import system, devices, sensors, measurements  # noqa: F401

router = APIRouter()
