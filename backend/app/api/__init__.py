from fastapi import APIRouter

router = APIRouter()

from . import system, devices, sensors, measurements  # noqa: F401
