from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.device import Device
from app.models.sensor import Sensor
from app.models.alarm_event import AlarmEvent
from app.schemas.alarm import (
    AlarmSettingsRead,
    AlarmSettingsUpdate,
    ActiveAlarmRead,
    AlarmHistoryRead,
    AlarmResetResponse,
)
from app.services.alarm_service import alarm_service


router = APIRouter(tags=["Alarms"])


@router.get("/alarms/settings", response_model=List[AlarmSettingsRead])
def get_alarm_settings(db: Session = Depends(get_db)):
    """Get alarm settings for all sensors."""
    sensors = db.query(Sensor).order_by(Sensor.id).all()
    result = []
    for sensor in sensors:
        device = db.query(Device).filter(Device.id == sensor.device_id).first()
        result.append(
            AlarmSettingsRead(
                sensor_id=sensor.id,
                device_id=sensor.device_id,
                sensor_name=sensor.name,
                device_name=device.name if device else "Unknown",
                device_display_name=device.display_name if device else None,
                current_temperature=sensor.last_value,
                alarm_enabled=sensor.alarm_enabled,
                alarm_low=sensor.alarm_low,
                alarm_high=sensor.alarm_high,
                alarm_activation_delay=sensor.alarm_activation_delay,
                alarm_state=sensor.alarm_state,
                alarm_level=sensor.alarm_level,
                alarm_no_data_enabled=sensor.alarm_no_data_enabled,
                alarm_no_data_timeout=sensor.alarm_no_data_timeout,
            )
        )
    return result


@router.post("/alarms/{alarm_id}/reset", response_model=AlarmResetResponse)
def reset_alarm(alarm_id: int, db: Session = Depends(get_db)):
    """Reset/acknowledge a single active alarm event.
    
    The alarm event is marked as CLEARED and the sensor state is reset to NORMAL.
    Alarm thresholds and configuration are preserved.
    If the alarm condition is still active, the next measurement will create a new alarm.
    """
    success = alarm_service.reset_alarm(alarm_id, session=db)
    if not success:
        raise HTTPException(status_code=404, detail="Active alarm not found or already cleared")
    return AlarmResetResponse(success=True, message=f"Alarm {alarm_id} reset successfully")


@router.post("/alarms/reset-all", response_model=AlarmResetResponse)
def reset_all_alarms(db: Session = Depends(get_db)):
    """Reset all currently active alarms.
    
    All active alarm events are marked as CLEARED and their sensor states are reset to NORMAL.
    Alarm thresholds and configuration are preserved.
    """
    count = alarm_service.reset_all_alarms(session=db)
    return AlarmResetResponse(
        success=True,
        message=f"{count} alarm(s) reset successfully",
        count=count,
    )



@router.put("/alarms/settings/{sensor_id}", response_model=AlarmSettingsRead)
def update_alarm_settings(sensor_id: int, payload: AlarmSettingsUpdate, db: Session = Depends(get_db)):
    """Update alarm settings for a specific sensor."""
    sensor = db.query(Sensor).filter(Sensor.id == sensor_id).one_or_none()
    if sensor is None:
        raise HTTPException(status_code=404, detail="Sensor not found")

    if payload.alarm_low is not None and payload.alarm_high is not None and payload.alarm_low >= payload.alarm_high:
        raise HTTPException(status_code=422, detail="alarm_low must be lower than alarm_high")

    sensor.alarm_enabled = payload.alarm_enabled
    sensor.alarm_low = payload.alarm_low
    sensor.alarm_high = payload.alarm_high
    sensor.alarm_activation_delay = payload.alarm_activation_delay
    sensor.alarm_no_data_enabled = payload.alarm_no_data_enabled
    sensor.alarm_no_data_timeout = payload.alarm_no_data_timeout

    db.commit()
    db.refresh(sensor)

    device = db.query(Device).filter(Device.id == sensor.device_id).first()
    return AlarmSettingsRead(
        sensor_id=sensor.id,
        device_id=sensor.device_id,
        sensor_name=sensor.name,
        device_name=device.name if device else "Unknown",
        device_display_name=device.display_name if device else None,
        current_temperature=sensor.last_value,
        alarm_enabled=sensor.alarm_enabled,
        alarm_low=sensor.alarm_low,
        alarm_high=sensor.alarm_high,
        alarm_activation_delay=sensor.alarm_activation_delay,
        alarm_state=sensor.alarm_state,
        alarm_level=sensor.alarm_level,
        alarm_no_data_enabled=sensor.alarm_no_data_enabled,
        alarm_no_data_timeout=sensor.alarm_no_data_timeout,
    )


@router.put("/alarms/settings", response_model=List[AlarmSettingsRead])
def update_all_alarm_settings(payload: List[AlarmSettingsUpdate], db: Session = Depends(get_db)):
    """Update alarm settings for all sensors in bulk."""
    result = []
    for update in payload:
        if update.sensor_id is None:
            raise HTTPException(status_code=422, detail="sensor_id is required for each settings update")

        sensor = db.query(Sensor).filter(Sensor.id == update.sensor_id).one_or_none()
        if sensor is None:
            raise HTTPException(status_code=404, detail=f"Sensor {update.sensor_id} not found")

        if update.alarm_low is not None and update.alarm_high is not None and update.alarm_low >= update.alarm_high:
            raise HTTPException(
                status_code=422,
                detail=f"alarm_low must be lower than alarm_high for sensor {update.sensor_id}",
            )

        sensor.alarm_enabled = update.alarm_enabled
        sensor.alarm_low = update.alarm_low
        sensor.alarm_high = update.alarm_high
        sensor.alarm_activation_delay = update.alarm_activation_delay
        sensor.alarm_no_data_enabled = update.alarm_no_data_enabled
        sensor.alarm_no_data_timeout = update.alarm_no_data_timeout

        db.commit()
        db.refresh(sensor)

        device = db.query(Device).filter(Device.id == sensor.device_id).first()
        result.append(
            AlarmSettingsRead(
                sensor_id=sensor.id,
                device_id=sensor.device_id,
                sensor_name=sensor.name,
                device_name=device.name if device else "Unknown",
                device_display_name=device.display_name if device else None,
                current_temperature=sensor.last_value,
                alarm_enabled=sensor.alarm_enabled,
                alarm_low=sensor.alarm_low,
                alarm_high=sensor.alarm_high,
                alarm_activation_delay=sensor.alarm_activation_delay,
                alarm_state=sensor.alarm_state,
                alarm_level=sensor.alarm_level,
                alarm_no_data_enabled=sensor.alarm_no_data_enabled,
                alarm_no_data_timeout=sensor.alarm_no_data_timeout,
            )
        )
    return result


@router.get("/alarms/active", response_model=List[ActiveAlarmRead])
def get_active_alarms(db: Session = Depends(get_db)):
    """Get currently active alarms."""
    active_states = ["PENDING_HIGH", "PENDING_LOW", "ALARM_HIGH", "ALARM_LOW", "NO_DATA"]

    events = (
        db.query(AlarmEvent)
        .filter(AlarmEvent.state.in_(active_states))
        .order_by(desc(AlarmEvent.id))
        .all()
    )

    result = []
    for event in events:
        sensor = db.query(Sensor).filter(Sensor.id == event.sensor_id).first()
        device = db.query(Device).filter(Device.id == event.device_id).first() if event.device_id else None
        result.append(
            ActiveAlarmRead(
                id=event.id,
                sensor_id=event.sensor_id,
                device_id=event.device_id,
                alarm_type=event.alarm_type,
                threshold=event.threshold,
                temperature=event.temperature,
                state=event.state,
                pending_start=event.pending_start,
                activated_at=event.activated_at,
                cleared_at=event.cleared_at,
                created_at=event.created_at,
                sensor_name=sensor.name if sensor else "Unknown",
                device_name=device.name if device else "Unknown",
                device_display_name=device.display_name if device else None,
            )
        )
    return result


@router.get("/alarms/history", response_model=List[AlarmHistoryRead])
def get_alarm_history(
    limit: int = Query(100, ge=1, le=1000),
    sensor_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """Get alarm history."""
    q = db.query(AlarmEvent).order_by(desc(AlarmEvent.id))
    if sensor_id is not None:
        q = q.filter(AlarmEvent.sensor_id == sensor_id)
    events = q.limit(limit).all()

    result = []
    for event in events:
        sensor = db.query(Sensor).filter(Sensor.id == event.sensor_id).first()
        device = db.query(Device).filter(Device.id == event.device_id).first() if event.device_id else None
        result.append(
            AlarmHistoryRead(
                id=event.id,
                sensor_id=event.sensor_id,
                device_id=event.device_id,
                alarm_type=event.alarm_type,
                threshold=event.threshold,
                temperature=event.temperature,
                state=event.state,
                pending_start=event.pending_start,
                activated_at=event.activated_at,
                cleared_at=event.cleared_at,
                created_at=event.created_at,
                sensor_name=sensor.name if sensor else "Unknown",
                device_name=device.name if device else "Unknown",
                device_display_name=device.display_name if device else None,
            )
        )
    return result
