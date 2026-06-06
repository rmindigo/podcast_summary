import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


def new_token() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    access_token: Mapped[str] = mapped_column(String(64), unique=True, default=new_token, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    channels: Mapped[list["Channel"]] = relationship("Channel", back_populates="user", cascade="all, delete-orphan")


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="channels")
