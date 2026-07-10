import math
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.measurement import Measurement
from app.schemas.measurement import MeasurementRead

router = APIRouter(tags=["Measurements"])


def _downsample_minmax(rows: list[Measurement], target_points: int) -> list[Measurement]:
    if target_points <= 0 or len(rows) <= target_points:
        return rows

    # Keep visual shape and extrema by returning min+max for each time bucket.
    bucket_count = max(1, target_points // 2)
    bucket_size = max(1, math.ceil(len(rows) / bucket_count))
    sampled: list[Measurement] = []

    for start in range(0, len(rows), bucket_size):
        bucket = rows[start:start + bucket_size]
        if not bucket:
            continue

        if len(bucket) == 1:
            sampled.append(bucket[0])
            continue

        minimum = min(bucket, key=lambda item: item.value)
        maximum = max(bucket, key=lambda item: item.value)

        if minimum.id == maximum.id:
            sampled.append(minimum)
            continue

        sampled.extend([minimum, maximum])

    sampled.sort(key=lambda item: (item.measured_at or datetime.min, item.id))
    return sampled[:target_points]


@router.get('/measurements/latest', response_model=List[MeasurementRead])
def latest_measurements(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    results = db.query(Measurement).order_by(desc(Measurement.measured_at)).limit(limit).all()
    return results


@router.get('/measurements/history', response_model=List[MeasurementRead])
def measurement_history(
    sensor_id: int | None = Query(None),
    from_ts: datetime | None = Query(None, alias="from"),
    to_ts: datetime | None = Query(None, alias="to"),
    skip: int = Query(0, ge=0),
    limit: int = Query(5000, ge=1, le=50000),
    target_points: int | None = Query(None, ge=100, le=5000),
    db: Session = Depends(get_db),
):
    if from_ts is not None and to_ts is not None and from_ts > to_ts:
        raise HTTPException(status_code=422, detail="'from' must be earlier than or equal to 'to'")

    q = db.query(Measurement)
    if sensor_id is not None:
        q = q.filter(Measurement.sensor_id == sensor_id)

    if from_ts is not None:
        q = q.filter(Measurement.measured_at >= from_ts)
    if to_ts is not None:
        q = q.filter(Measurement.measured_at <= to_ts)

    rows = q.order_by(Measurement.measured_at, Measurement.id).offset(skip).limit(limit).all()

    if target_points is not None:
        rows = _downsample_minmax(rows, target_points)

    return rows
