"""Fixed-window rate limiting stored in the database.

Serverless instances don't share memory, so counters live in a table every instance can see.
"""
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import models


def check(db: Session, bucket: str, limit: int, window: timedelta) -> None:
    since = datetime.utcnow() - window
    n = db.scalar(
        select(func.count()).select_from(models.RateEvent)
        .where(models.RateEvent.bucket == bucket, models.RateEvent.created_at >= since)
    )
    if n >= limit:
        minutes = max(1, int(window.total_seconds() // 60))
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many attempts. Try again in {minutes} minutes.",
            headers={"Retry-After": str(int(window.total_seconds()))},
        )


def record(db: Session, bucket: str) -> None:
    db.execute(delete(models.RateEvent).where(
        models.RateEvent.bucket == bucket, models.RateEvent.created_at < datetime.utcnow() - timedelta(days=1)
    ))
    db.add(models.RateEvent(bucket=bucket))
    db.commit()
