from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.schemas.device import DeviceRead

router = APIRouter(tags=["Devices"])


@router.get('/devices', response_model=List[DeviceRead])
def list_devices(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    devices = db.query(Device).offset(skip).limit(limit).all()
    return devices


@router.get('/devices/{device_id}', response_model=DeviceRead)
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail='Device not found')
    return device
