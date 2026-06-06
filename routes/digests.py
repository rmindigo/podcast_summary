import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from database import get_db
from models import User, Digest

router = APIRouter(prefix="/api/digests", tags=["digests"])


def _get_user(authorization: Optional[str], db: Session) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.removeprefix("Bearer ").strip()
    user = db.query(User).filter(User.access_token == token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


@router.get("")
def list_digests(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _get_user(authorization, db)
    digests = (
        db.query(Digest)
        .filter(Digest.user_id == user.id)
        .order_by(Digest.sent_at.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "sent_at": d.sent_at.isoformat(),
            "episode_count": d.episode_count,
            "week_label": json.loads(d.content_json).get("week_label", ""),
        }
        for d in digests
    ]


@router.get("/{digest_id}")
def get_digest(digest_id: int, authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    user = _get_user(authorization, db)
    digest = db.query(Digest).filter(Digest.id == digest_id, Digest.user_id == user.id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    return json.loads(digest.content_json)
