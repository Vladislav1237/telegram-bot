"""
Database models for the Telegram bot.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, 
    ForeignKey, Text, Enum as SQLEnum
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class UserStatus(enum.Enum):
    """User status enumeration."""
    ACTIVE = "active"
    BANNED = "banned"
    DEACTIVATED = "deactivated"


class TaskStatus(enum.Enum):
    """Task status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WithdrawalStatus(enum.Enum):
    """Withdrawal status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    language_code = Column(String(10), default="en")
    
    # Economy
    balance = Column(Float, default=0.0)
    frozen_balance = Column(Float, default=0.0)
    
    # Referral system
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    referred_users = relationship("User", backref="referrer", remote_side=[id])
    
    # Subscription
    is_subscribed = Column(Boolean, default=False)
    subscription_start = Column(DateTime, nullable=True)
    subscription_end = Column(DateTime, nullable=True)
    last_reward_claim = Column(DateTime, nullable=True)
    
    # Status
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE)
    
    # Violation tracking
    violation_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan", foreign_keys="Task.user_id")
    withdrawals = relationship(
        "Withdrawal", back_populates="user", cascade="all, delete-orphan", foreign_keys="Withdrawal.user_id"
    )
    promo_uses = relationship(
        "PromoCodeUse", back_populates="user", cascade="all, delete-orphan", foreign_keys="PromoCodeUse.user_id"
    )


class Task(Base):
    """Task model — created by admin, completed by users."""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    chat_id = Column(String(50), nullable=True)
    bot_username = Column(String(255), nullable=True)
    screenshot_file_id = Column(String(255), nullable=True)
    reward = Column(Float, default=0.0)
    category = Column(String(50), default="subscribe")
    check_type = Column(String(20), default="auto")  # "auto" or "manual"
    is_active = Column(Boolean, default=True)
    
    # Status
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.APPROVED)
    admin_comment = Column(Text, nullable=True)
    
    # Admin review
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="tasks", foreign_keys=[user_id])
    completions = relationship("TaskCompletion", back_populates="task")


class TaskCompletion(Base):
    """Tracks user task completions (pending admin approval)."""
    __tablename__ = "task_completions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    screenshot_file_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    task = relationship("Task", back_populates="completions")
    user = relationship("User")


class Withdrawal(Base):
    """Withdrawal model for TON withdrawals."""
    __tablename__ = "withdrawals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    wallet_address = Column(String(255), nullable=False)
    
    # Status
    status = Column(SQLEnum(WithdrawalStatus), default=WithdrawalStatus.PENDING)
    admin_comment = Column(Text, nullable=True)
    
    # Transaction
    transaction_hash = Column(String(255), nullable=True)
    
    # Admin review
    processed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="withdrawals", foreign_keys=[user_id])


class PromoCode(Base):
    """Promo code model."""
    __tablename__ = "promo_codes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    reward_amount = Column(Float, nullable=False)
    max_uses = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    # Expiration
    expires_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    uses = relationship("PromoCodeUse", back_populates="promo_code")


class PromoCodeUse(Base):
    """Promo code usage tracking."""
    __tablename__ = "promo_code_uses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Timestamps
    used_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    promo_code = relationship("PromoCode", back_populates="uses", foreign_keys=[promo_code_id])
    user = relationship("User", back_populates="promo_uses", foreign_keys=[user_id])


class AdminLog(Base):
    """Admin action logging."""
    __tablename__ = "admin_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, nullable=False)
    action = Column(String(255), nullable=False)
    target_type = Column(String(50), nullable=True)
    target_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
