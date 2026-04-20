from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from backend.src.db.database import get_db
from backend.src.db.models import CallRecord, User, CallMetrics, UserAnalytics
from backend.src.auth import get_current_user

router = APIRouter()


class AnalyticsSnapshot(BaseModel):
    total_calls: int
    total_minutes: float
    avg_pace: Optional[float]
    avg_clarity: Optional[float]
    improvement_pct: Optional[float]


class CallStats(BaseModel):
    avg_words_per_minute: Optional[float]
    avg_filler_words: Optional[int]
    avg_articulation_score: Optional[float]
    avg_confidence_score: Optional[float]


@router.get("/summary", response_model=AnalyticsSnapshot)
async def get_analytics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's analytics summary."""
    # Total calls and minutes
    calls = db.query(CallRecord).filter(
        CallRecord.user_id == current_user.id
    ).all()

    total_calls = len(calls)
    total_minutes = sum(call.duration_seconds or 0 for call in calls) / 60.0

    # Average metrics
    metrics = db.query(CallMetrics).filter(
        CallMetrics.call_record_id.in_([call.id for call in calls])
    ).all()

    avg_pace = None
    avg_clarity = None

    if metrics:
        pace_values = [m.words_per_minute for m in metrics if m.words_per_minute]
        clarity_values = [m.articulation_score for m in metrics if m.articulation_score]

        if pace_values:
            avg_pace = sum(pace_values) / len(pace_values)
        if clarity_values:
            avg_clarity = sum(clarity_values) / len(clarity_values)

    return {
        "total_calls": total_calls,
        "total_minutes": total_minutes,
        "avg_pace": avg_pace,
        "avg_clarity": avg_clarity,
        "improvement_pct": None  # Would be calculated with baseline
    }


@router.get("/trends")
async def get_trends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = 30
):
    """Get analytics trends over time."""
    since = datetime.utcnow() - timedelta(days=days)

    calls = db.query(CallRecord).filter(
        CallRecord.user_id == current_user.id,
        CallRecord.started_at >= since
    ).order_by(CallRecord.started_at).all()

    trend_data = []
    for call in calls:
        metrics = db.query(CallMetrics).filter(
            CallMetrics.call_record_id == call.id
        ).all()

        if metrics:
            avg_pace = sum(m.words_per_minute for m in metrics if m.words_per_minute) / len([m for m in metrics if m.words_per_minute]) if any(m.words_per_minute for m in metrics) else None
            avg_confidence = sum(m.confidence_score for m in metrics if m.confidence_score) / len([m for m in metrics if m.confidence_score]) if any(m.confidence_score for m in metrics) else None

            trend_data.append({
                "date": call.started_at.isoformat(),
                "call_id": call.id,
                "duration_seconds": call.duration_seconds,
                "avg_pace": avg_pace,
                "avg_confidence": avg_confidence,
            })

    return trend_data


@router.get("/call/{call_id}/summary")
async def get_call_summary(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get summary for a specific call."""
    call = db.query(CallRecord).filter(
        CallRecord.id == call_id,
        CallRecord.user_id == current_user.id
    ).first()

    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    metrics = db.query(CallMetrics).filter(
        CallMetrics.call_record_id == call_id
    ).all()

    if not metrics:
        return {
            "call_id": call_id,
            "duration_seconds": call.duration_seconds,
            "metrics": {}
        }

    avg_pace = sum(m.words_per_minute for m in metrics if m.words_per_minute) / len([m for m in metrics if m.words_per_minute]) if any(m.words_per_minute for m in metrics) else None
    total_fillers = sum(m.filler_word_count for m in metrics if m.filler_word_count)
    avg_confidence = sum(m.confidence_score for m in metrics if m.confidence_score) / len([m for m in metrics if m.confidence_score]) if any(m.confidence_score for m in metrics) else None
    avg_clarity = sum(m.articulation_score for m in metrics if m.articulation_score) / len([m for m in metrics if m.articulation_score]) if any(m.articulation_score for m in metrics) else None

    return {
        "call_id": call_id,
        "duration_seconds": call.duration_seconds,
        "metrics": {
            "avg_words_per_minute": avg_pace,
            "total_filler_words": total_fillers,
            "avg_confidence_score": avg_confidence,
            "avg_clarity_score": avg_clarity,
        }
    }
