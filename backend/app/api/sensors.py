from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.sensor import Sensor
from app.schemas.sensor import SensorAlarmUpdate, SensorRead, SensorUpdate

router = APIRouter(tags=["Sensors"])


@router.get('/sensors', response_model=List[SensorRead])
def list_sensors(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    sensors = db.query(Sensor).offset(skip).limit(limit).all()
    return sensors


@router.get('/sensors/{sensor_id}', response_model=SensorRead)
def get_sensor(sensor_id: int, db: Session = Depends(get_db)):
    sensor = db.query(Sensor).filter(Sensor.id == sensor_id).one_or_none()
    if sensor is None:
        raise HTTPException(status_code=404, detail='Sensor not found')
    return sensor


@router.put('/sensors/{sensor_id}', response_model=SensorRead)
def update_sensor(sensor_id: int, payload: SensorUpdate, db: Session = Depends(get_db)):
    sensor = db.query(Sensor).filter(Sensor.id == sensor_id).one_or_none()
    if sensor is None:
        raise HTTPException(status_code=404, detail='Sensor not found')

    for field, value in payload.model_dump(exclude_unset=True).items():
        # Trim whitespace from string fields
        if isinstance(value, str):
            value = value.strip()
        setattr(sensor, field, value)

    db.commit()
    db.refresh(sensor)
    return sensor


@router.put('/sensors/{sensor_id}/alarm', response_model=SensorRead)
def update_sensor_alarm(sensor_id: int, payload: SensorAlarmUpdate, db: Session = Depends(get_db)):
    sensor = db.query(Sensor).filter(Sensor.id == sensor_id).one_or_none()
    if sensor is None:
        raise HTTPException(status_code=404, detail='Sensor not found')

    if payload.alarm_low is not None and payload.alarm_high is not None and payload.alarm_low >= payload.alarm_high:
        raise HTTPException(status_code=422, detail='alarm_low must be lower than alarm_high')

    sensor.alarm_enabled = payload.alarm_enabled
    sensor.alarm_low = payload.alarm_low
    sensor.alarm_high = payload.alarm_high
    sensor.alarm_hysteresis = payload.alarm_hysteresis
    sensor.alarm_activation_delay = payload.alarm_activation_delay

    db.commit()
    db.refresh(sensor)
    return sensor
