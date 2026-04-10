from datetime import datetime
from enum import Enum
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.engine import BaseModel


class TaskStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WithdrawalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(BaseModel):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    frozen_balance: Mapped[float] = mapped_column(Float, default=0.0)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    total_referrals: Mapped[int] = mapped_column(Integer, default=0)
    total_earned: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    is_subscribed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_subscription_check: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )


class Task(BaseModel):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    reward: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(50), default="custom")
    check_type: Mapped[str] = mapped_column(String(20), default="manual")
    target_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class UserTask(BaseModel):
    __tablename__ = "user_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"))
    screenshot_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, onupdate=func.now()
    )


class Withdrawal(BaseModel):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount: Mapped[float] = mapped_column(Float)
    address: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(20), default=WithdrawalStatus.PENDING.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PromoCode(BaseModel):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    reward: Mapped[float] = mapped_column(Float)
    uses_left: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(BigInteger)


class SubscriptionReward(BaseModel):
    __tablename__ = "subscription_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="frozen")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    unfreeze_at: Mapped[datetime] = mapped_column(DateTime)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
