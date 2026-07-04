from fastapi import APIRouter, Depends, Query
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.measurement import Measurement
from app.schemas.measurement import MeasurementRead

router = APIRouter(tags=["Measurements"])


@router.get('/measurements/latest', response_model=List[MeasurementRead])
def latest_measurements(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    results = db.query(Measurement).order_by(desc(Measurement.measured_at)).limit(limit).all()
    return results


@router.get('/measurements/history', response_model=List[MeasurementRead])
def measurement_history(sensor_id: int | None = Query(None), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    q = db.query(Measurement)
    if sensor_id is not None:
        q = q.filter(Measurement.sensor_id == sensor_id)
    q = q.order_by(Measurement.measured_at).offset(skip).limit(limit)
    return q.all()
