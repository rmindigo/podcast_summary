from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import User, Channel
from services.transcripts import get_channel_display_name, normalize_channel_url, get_channel_videos

router = APIRouter(prefix="/api/channels", tags=["channels"])


def _get_user(authorization: Optional[str], db: Session) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.removeprefix("Bearer ").strip()
    user = db.query(User).filter(User.access_token == token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


class AddChannelRequest(BaseModel):
    url: str


@router.get("")
def list_channels(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _get_user(authorization, db)
    channels = [c for c in user.channels if c.active]
    return [{"id": c.id, "name": c.name, "url": c.url, "created_at": c.created_at.isoformat()} for c in channels]


@router.post("")
def add_channel(req: AddChannelRequest, authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _get_user(authorization, db)

    url = normalize_channel_url(req.url)

    # Validate it looks like a YouTube channel URL
    if "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(status_code=400, detail="Please provide a YouTube channel URL.")

    # Check for duplicate
    existing = db.query(Channel).filter(
        Channel.user_id == user.id,
        Channel.url == url,
        Channel.active == True,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="You're already subscribed to this channel.")

    # Try to validate the channel exists and get recent videos (lightweight check)
    try:
        videos = get_channel_videos(url, limit=15)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    name = get_channel_display_name(url)

    channel = Channel(user_id=user.id, url=url, name=name)
    db.add(channel)
    db.commit()
    db.refresh(channel)

    return {
        "id": channel.id,
        "name": channel.name,
        "url": channel.url,
        "recent_videos": len(videos),
        "message": f"Added {channel.name}. Found {len(videos)} video(s) in the last 30 days.",
    }


@router.delete("/{channel_id}")
def remove_channel(channel_id: int, authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _get_user(authorization, db)
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == user.id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    channel.active = False
    db.commit()
    return {"message": f"Removed {channel.name}"}
