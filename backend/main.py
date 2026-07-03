from fastapi import FastAPI
from app.config import settings
from app.logger import logger

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

@app.on_event("startup")
def startup():
    logger.info("FrigoMonitor starting...")

@app.get("/")
def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}

@app.get("/health")
def health():
    return {"status":"ok"}
