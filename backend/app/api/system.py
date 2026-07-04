from fastapi import APIRouter
from app.config import settings

router = APIRouter(tags=["System"])


@router.get('/system/health')
def health():
    return {"status": "ok", "app": settings.APP_NAME}
