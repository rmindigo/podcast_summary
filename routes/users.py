from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from database import get_db
from models import User, new_token
from services.email_service import send_welcome, send_magic_link

router = APIRouter(prefix="/api", tags=["users"])


class SignupRequest(BaseModel):
    email: EmailStr


class ResendRequest(BaseModel):
    email: EmailStr


@router.post("/signup")
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        # Already registered — just resend their link
        send_magic_link(existing.email, existing.access_token)
        return {"status": "existing", "message": "We found your account. Check your email for your dashboard link."}

    user = User(email=req.email)
    db.add(user)
    db.commit()
    db.refresh(user)

    send_welcome(user.email, user.access_token)
    return {"status": "created", "message": "Account created! Check your email for your dashboard link."}


@router.post("/resend-link")
def resend_link(req: ResendRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        # Don't reveal whether the email exists
        return {"message": "If that email is registered, we sent your dashboard link."}
    send_magic_link(user.email, user.access_token)
    return {"message": "Dashboard link sent. Check your email."}


@router.get("/me")
def get_me(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.access_token == token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {
        "email": user.email,
        "created_at": user.created_at.isoformat(),
        "channel_count": len([c for c in user.channels if c.active]),
    }


@router.post("/unsubscribe")
def unsubscribe(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.access_token == token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    user.active = False
    db.commit()
    return {"message": "Unsubscribed. You will no longer receive weekly digests."}
