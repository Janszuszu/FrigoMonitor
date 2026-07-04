from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.logger import logger
from app.api import system, devices, sensors, measurements
from app.ws.websocket_manager import router as websocket_router


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
