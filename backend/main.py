from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine
from app.logger import logger
from app.api import system, devices, sensors, measurements, alarms, telegram
from app.services.device_manager import device_manager as _device_manager
from app.services.modbus_rtu_service import modbus_rtu_service
from app.services.nt57b08_service import nt57b08_service
from app.services.mqtt_service import mqtt_service
from app.ws.websocket_manager import router as websocket_router

_ = _device_manager


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    logger.info("FrigoMonitor starting...")
    Base.metadata.create_all(bind=engine)
    mqtt_service.connect()
    modbus_rtu_service.start()
    nt57b08_service.start()


@app.on_event("shutdown")
def shutdown():
    nt57b08_service.stop()
    modbus_rtu_service.stop()
    mqtt_service.disconnect()


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
app.include_router(alarms.router, prefix="/api/v1")
app.include_router(telegram.router, prefix="/api/v1")
app.include_router(websocket_router)
