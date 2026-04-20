from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from backend.src.db.database import get_db
from backend.src.db.models import CallRecord, User, CallType, CallMetrics, CallFeedback
from backend.src.auth import get_current_user

router = APIRouter()


class CallStart(BaseModel):
    profile_id: str
    call_type: str  # 'phone', 'video', 'simulation'
    external_participant_name: Optional[str] = None


class CallMetricsData(BaseModel):
    words_per_minute: Optional[float] = None
    avg_pause_duration_ms: Optional[int] = None
    filler_word_count: Optional[int] = None
    speech_rate: Optional[int] = None
    volume_variance: Optional[float] = None
    articulation_score: Optional[float] = None
    confidence_score: Optional[float] = None
    energy_level: Optional[float] = None
    stress_level: Optional[float] = None


class CallRecord(BaseModel):
    id: str
    call_type: str
    external_participant_name: Optional[str]
    duration_seconds: int
    transcript: Optional[str]
    started_at: str
    ended_at: Optional[str]
    is_archived: bool

    class Config:
        from_attributes = True


class CallResponse(BaseModel):
    id: str
    call_type: str
    external_participant_name: Optional[str]
    duration_seconds: int
    transcript: Optional[str]
    audio_s3_url: Optional[str]
    started_at: str
    ended_at: Optional[str]
    is_archived: bool

    class Config:
        from_attributes = True


@router.post("/start")
async def start_call(
    call_data: CallStart,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start a new call session."""
    new_call = CallRecord(
        user_id=current_user.id,
        profile_id=call_data.profile_id,
        call_type=call_data.call_type,
        external_participant_name=call_data.external_participant_name,
    )
    db.add(new_call)
    db.commit()
    db.refresh(new_call)

    return {
        "call_id": new_call.id,
        "started_at": new_call.started_at.isoformat()
    }


@router.post("/{call_id}/end")
async def end_call(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """End a call session."""
    call = db.query(CallRecord).filter(
        CallRecord.id == call_id,
        CallRecord.user_id == current_user.id
    ).first()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    call.ended_at = datetime.utcnow()
    if call.ended_at and call.started_at:
        call.duration_seconds = int((call.ended_at - call.started_at).total_seconds())

    db.commit()
    db.refresh(call)

    return {
        "call_id": call.id,
        "duration_seconds": call.duration_seconds,
        "ended_at": call.ended_at.isoformat()
    }


@router.post("/{call_id}/metrics")
async def add_metrics(
    call_id: str,
    metrics_data: CallMetricsData,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add metrics snapshot for a call."""
    call = db.query(CallRecord).filter(
        CallRecord.id == call_id,
        CallRecord.user_id == current_user.id
    ).first()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    metrics = CallMetrics(
        call_record_id=call_id,
        words_per_minute=metrics_data.words_per_minute,
        avg_pause_duration_ms=metrics_data.avg_pause_duration_ms,
        filler_word_count=metrics_data.filler_word_count,
        speech_rate=metrics_data.speech_rate,
        volume_variance=metrics_data.volume_variance,
        articulation_score=metrics_data.articulation_score,
        confidence_score=metrics_data.confidence_score,
        energy_level=metrics_data.energy_level,
        stress_level=metrics_data.stress_level,
    )
    db.add(metrics)
    db.commit()

    return {"status": "metrics recorded"}


@router.post("/{call_id}/transcript")
async def add_transcript(
    call_id: str,
    transcript: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update call transcript."""
    call = db.query(CallRecord).filter(
        CallRecord.id == call_id,
        CallRecord.user_id == current_user.id
    ).first()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    call.transcript = transcript
    db.commit()

    return {"status": "transcript updated"}


@router.get("/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get call details."""
    call = db.query(CallRecord).filter(
        CallRecord.id == call_id,
        CallRecord.user_id == current_user.id
    ).first()
    if not call:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    return call


@router.get("", response_model=List[CallResponse])
async def list_calls(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0
):
    """List user's calls."""
    calls = db.query(CallRecord).filter(
        CallRecord.user_id == current_user.id
    ).order_by(CallRecord.started_at.desc()).limit(limit).offset(offset).all()

    return calls
