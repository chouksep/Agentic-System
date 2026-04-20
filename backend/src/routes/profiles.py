from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from backend.src.db.database import get_db
from backend.src.db.models import CoachingProfile, User, ProfileType
from backend.src.auth import get_current_user

router = APIRouter()


class CoachingProfileCreate(BaseModel):
    name: str
    profile_type: str  # 'interview', 'sales', 'presentation', 'custom'
    coaching_focus: Optional[dict] = None
    instructions: Optional[str] = None


class CoachingProfileUpdate(BaseModel):
    name: Optional[str] = None
    coaching_focus: Optional[dict] = None
    instructions: Optional[str] = None
    is_active: Optional[bool] = None


class CoachingProfileResponse(BaseModel):
    id: str
    name: str
    profile_type: str
    coaching_focus: dict
    instructions: Optional[str] = None
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


@router.post("", response_model=CoachingProfileResponse)
async def create_profile(
    profile_data: CoachingProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new coaching profile."""
    # Set default coaching focus based on profile type
    coaching_focus = profile_data.coaching_focus or {
        "pace": True,
        "clarity": True,
        "fillers": True,
        "confidence": True
    }

    # Set default instructions based on profile type
    instructions = profile_data.instructions or get_default_instructions(profile_data.profile_type)

    new_profile = CoachingProfile(
        user_id=current_user.id,
        name=profile_data.name,
        profile_type=profile_data.profile_type,
        coaching_focus=coaching_focus,
        instructions=instructions,
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return new_profile


@router.get("", response_model=List[CoachingProfileResponse])
async def list_profiles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all coaching profiles for user."""
    profiles = db.query(CoachingProfile).filter(
        CoachingProfile.user_id == current_user.id
    ).all()
    return profiles


@router.get("/{profile_id}", response_model=CoachingProfileResponse)
async def get_profile(
    profile_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific coaching profile."""
    profile = db.query(CoachingProfile).filter(
        CoachingProfile.id == profile_id,
        CoachingProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.put("/{profile_id}", response_model=CoachingProfileResponse)
async def update_profile(
    profile_id: str,
    update_data: CoachingProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a coaching profile."""
    profile = db.query(CoachingProfile).filter(
        CoachingProfile.id == profile_id,
        CoachingProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    if update_data.name:
        profile.name = update_data.name
    if update_data.coaching_focus:
        profile.coaching_focus = update_data.coaching_focus
    if update_data.instructions:
        profile.instructions = update_data.instructions
    if update_data.is_active is not None:
        profile.is_active = update_data.is_active

    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a coaching profile."""
    profile = db.query(CoachingProfile).filter(
        CoachingProfile.id == profile_id,
        CoachingProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    db.delete(profile)
    db.commit()
    return {"message": "Profile deleted"}


def get_default_instructions(profile_type: str) -> str:
    """Get default Claude instructions for profile type."""
    instructions = {
        "interview": """You are a professional interview coach. Provide real-time coaching tips
        to help the user improve their interview performance. Focus on: speaking pace, clarity,
        confidence, and reducing filler words. Keep tips concise (1-2 sentences) and actionable.""",

        "sales": """You are a sales coaching expert. Provide real-time tips to help the user
        improve their sales pitch. Focus on: persuasiveness, clarity, energy level, and
        engaging the listener. Keep tips concise and focused on sales techniques.""",

        "presentation": """You are a presentation coach. Help the user deliver better presentations
        in real-time. Focus on: pacing, clarity, confidence, and audience engagement.
        Keep tips actionable and concise.""",

        "custom": """You are a communication coach providing real-time coaching feedback."""
    }
    return instructions.get(profile_type, instructions["custom"])
