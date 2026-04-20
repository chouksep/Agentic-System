from sqlalchemy import Column, String, Integer, DateTime, Boolean, Float, JSON, Enum, ForeignKey, Text, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

Base = declarative_base()


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    PREMIUM = "premium"


class ProfileType(str, enum.Enum):
    INTERVIEW = "interview"
    SALES = "sales"
    PRESENTATION = "presentation"
    CUSTOM = "custom"


class CallType(str, enum.Enum):
    PHONE = "phone"
    VIDEO = "video"
    SIMULATION = "simulation"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True)
    phone_number = Column(String(20), unique=True, nullable=True, index=True)
    display_name = Column(String(255))
    hashed_password = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    subscription_tier = Column(Enum(SubscriptionTier), default=SubscriptionTier.FREE)
    onboarding_complete = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Relationships
    coaching_profiles = relationship("CoachingProfile", back_populates="user")
    call_records = relationship("CallRecord", back_populates="user")
    user_analytics = relationship("UserAnalytics", back_populates="user", uselist=False)


class CoachingProfile(Base):
    __tablename__ = "coaching_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    profile_type = Column(Enum(ProfileType), nullable=False)
    coaching_focus = Column(JSON, default={})  # { "pace": true, "clarity": true, ... }
    instructions = Column(Text)  # Claude system prompt customization
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="coaching_profiles")
    call_records = relationship("CallRecord", back_populates="coaching_profile")


class CallRecord(Base):
    __tablename__ = "call_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    profile_id = Column(String(36), ForeignKey("coaching_profiles.id"), nullable=True)
    call_type = Column(Enum(CallType), nullable=False)
    external_participant_name = Column(String(255), nullable=True)
    duration_seconds = Column(Integer, default=0)
    transcript = Column(Text, nullable=True)
    audio_s3_url = Column(String(500), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="call_records")
    coaching_profile = relationship("CoachingProfile", back_populates="call_records")
    metrics = relationship("CallMetrics", back_populates="call_record")
    tips = relationship("RealTimeTip", back_populates="call_record")
    feedback = relationship("CallFeedback", back_populates="call_record", uselist=False)


class CallMetrics(Base):
    __tablename__ = "call_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    call_record_id = Column(String(36), ForeignKey("call_records.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Pace metrics
    words_per_minute = Column(Float, nullable=True)
    avg_pause_duration_ms = Column(Integer, nullable=True)
    filler_word_count = Column(Integer, default=0)

    # Clarity metrics
    speech_rate = Column(Integer, nullable=True)  # syllables per minute
    volume_variance = Column(Float, nullable=True)
    articulation_score = Column(Float, nullable=True)

    # Emotion/Prosody
    confidence_score = Column(Float, nullable=True)
    energy_level = Column(Float, nullable=True)
    stress_level = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    call_record = relationship("CallRecord", back_populates="metrics")


class RealTimeTip(Base):
    __tablename__ = "real_time_tips"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    call_record_id = Column(String(36), ForeignKey("call_records.id"), nullable=False, index=True)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    trigger_reason = Column(String(100), nullable=False)
    tip_text = Column(Text, nullable=False)
    tip_category = Column(String(50), nullable=False)
    user_interacted = Column(Boolean, default=False)
    interaction_type = Column(String(50), nullable=True)  # 'dismissed', 'saved', 'acted_on'

    # Relationships
    call_record = relationship("CallRecord", back_populates="tips")


class CallFeedback(Base):
    __tablename__ = "call_feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    call_record_id = Column(String(36), ForeignKey("call_records.id"), nullable=False, index=True, unique=True)
    generated_at = Column(DateTime, default=datetime.utcnow)

    # Structured feedback
    summary_html = Column(Text, nullable=True)
    strengths = Column(JSON, default=[])  # array of strength objects
    improvement_areas = Column(JSON, default=[])  # array of improvement objects

    # Metrics summary
    overall_score = Column(Float, nullable=True)
    comparative_baseline = Column(JSON, nullable=True)

    # User reactions
    user_rating = Column(Integer, nullable=True)  # 1-5
    user_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    call_record = relationship("CallRecord", back_populates="feedback")


class UserAnalytics(Base):
    __tablename__ = "user_analytics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # Running tallies
    total_calls = Column(Integer, default=0)
    total_minutes = Column(Float, default=0)
    avg_pace = Column(Float, nullable=True)
    avg_clarity = Column(Float, nullable=True)

    # Progress tracking
    baseline_metrics = Column(JSON, nullable=True)  # first 3 calls
    latest_metrics = Column(JSON, nullable=True)  # last call
    improvement_pct = Column(Float, nullable=True)

    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="user_analytics", uselist=False)
