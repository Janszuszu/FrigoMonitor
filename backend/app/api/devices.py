from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.sensor import Sensor
from app.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate
from app.schemas.sensor import SensorCreate, SensorRead

router = APIRouter(tags=["Devices"])


@router.get('/devices', response_model=List[DeviceRead])
def list_devices(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    devices = db.query(Device).offset(skip).limit(limit).all()
    return devices


@router.post('/devices', response_model=DeviceRead, status_code=201)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)):
    existing = db.query(Device).filter(Device.serial_number == payload.serial_number).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail='Device serial_number already exists')

    device = Device(name=payload.name, serial_number=payload.serial_number, location=payload.location)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get('/devices/{device_id}', response_model=DeviceRead)
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail='Device not found')
    return device


@router.put('/devices/{device_id}', response_model=DeviceRead)
def update_device(device_id: int, payload: DeviceUpdate, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail='Device not found')

    if payload.serial_number and payload.serial_number != device.serial_number:
        existing = db.query(Device).filter(Device.serial_number == payload.serial_number).one_or_none()
        if existing is not None:
            raise HTTPException(status_code=409, detail='Device serial_number already exists')

    for field, value in payload.model_dump(exclude_unset=True).items():
        # Trim whitespace from string fields
        if isinstance(value, str):
            value = value.strip()
        setattr(device, field, value)

    db.commit()
    db.refresh(device)
    return device


@router.post('/devices/{device_id}/sensors', response_model=SensorRead, status_code=201)
def create_device_sensor(device_id: int, payload: SensorCreate, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail='Device not found')

    existing = db.query(Sensor).filter(Sensor.device_id == device_id, Sensor.name == payload.name).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail='Sensor name already exists for device')

    sensor = Sensor(
        device_id=device_id,
        name=payload.name,
        sensor_type=payload.sensor_type,
        address=payload.address,
        correction=payload.correction,
    )
    db.add(sensor)
    db.commit()
    db.refresh(sensor)
    return sensor
