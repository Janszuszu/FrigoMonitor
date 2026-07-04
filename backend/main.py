from fastapi import FastAPI
from app.config import settings
from app.logger import logger
from app.api import system, devices, sensors, measurements
from app.ws.websocket_manager import router as websocket_router


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)


@app.on_event("startup")
def startup():
    logger.info("FrigoMonitor starting...")


@app.get("/")
def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}


# Register API routers under /api/v1
app.include_router(system.router, prefix="/api/v1")
app.include_router(devices.router, prefix="/api/v1")
app.include_router(sensors.router, prefix="/api/v1")
app.include_router(measurements.router, prefix="/api/v1")
app.include_router(websocket_router)
