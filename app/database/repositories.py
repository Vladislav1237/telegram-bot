"""
Repository pattern for database operations.
"""
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List

from app.models import (
    User, Task, TaskCompletion, Withdrawal, 
    PromoCode, PromoCodeUse, AdminLog, Sponsor,
    TaskStatus, WithdrawalStatus, UserStatus
)


class UserRepository:
    """User repository for database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def create(self, **kwargs) -> User:
        user = User(**kwargs)
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user
    
    async def update_balance(self, user_id: int, amount: float, freeze: bool = False) -> User:
        user = await self.get_by_id(user_id)
        if user:
            if freeze:
                user.frozen_balance += amount
            else:
                user.balance += amount
            await self.session.flush()
            await self.session.refresh(user)
        return user
    
    async def deduct_balance(self, user_id: int, amount: float) -> User:
        user = await self.get_by_id(user_id)
        if user:
            user.balance = max(0, user.balance - amount)
            await self.session.flush()
            await self.session.refresh(user)
        return user
    
    async def update_subscription_status(self, user_id: int, is_sub: bool) -> User:
        user = await self.get_by_id(user_id)
        if user:
            user.is_subscribed = is_sub
            if is_sub:
                user.subscription_start = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(user)
        return user
    
    async def update_last_reward_claim(self, user_id: int) -> User:
        user = await self.get_by_id(user_id)
        if user:
            user.last_reward_claim = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(user)
        return user
    
    async def get_referral_count(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count(User.id)).where(User.referrer_id == user_id)
        )
        return result.scalar() or 0
    
    async def get_all_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        result = await self.session.execute(
            select(User).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
    
    async def get_users_count(self) -> int:
        result = await self.session.execute(
            select(func.count(User.id))
        )
        return result.scalar() or 0


class TaskRepository:
    """Task repository for database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, task_id: int) -> Optional[Task]:
        result = await self.session.execute(
            select(Task).where(Task.id == task_id)
        )
        return result.scalar_one_or_none()
    
    async def get_pending_tasks(self) -> List[Task]:
        result = await self.session.execute(
            select(Task)
            .where(Task.status == TaskStatus.PENDING)
            .order_by(Task.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_active_by_category(self, category: str) -> List[Task]:
        result = await self.session.execute(
            select(Task)
            .where(Task.category == category)
            .where(Task.is_active == True)
            .order_by(Task.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_active_by_category_except_completed(self, category: str, user_id: int) -> List[Task]:
        result = await self.session.execute(
            select(Task)
            .where(Task.category == category)
            .where(Task.is_active == True)
            .where(Task.id.notin_(
                select(TaskCompletion.task_id).where(TaskCompletion.user_id == user_id)
            ))
            .order_by(Task.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def create(self, **kwargs) -> Task:
        task = Task(**kwargs)
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task
    
    async def update_status(self, task_id: int, status: TaskStatus, admin_comment: str = None, reviewed_by: int = None) -> Task:
        task = await self.get_by_id(task_id)
        if task:
            task.status = status
            if admin_comment:
                task.admin_comment = admin_comment
            if reviewed_by:
                task.reviewed_by = reviewed_by
                task.reviewed_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(task)
        return task
    
    async def get_user_task_completion(self, user_id: int, task_id: int) -> Optional[TaskCompletion]:
        result = await self.session.execute(
            select(TaskCompletion)
            .where(TaskCompletion.user_id == user_id)
            .where(TaskCompletion.task_id == task_id)
        )
        return result.scalar_one_or_none()
    
    async def create_completion(self, user_id: int, task_id: int, screenshot_file_id: str = None, forwarded_from_chat_id: int = None, screenshots_count: int = 0) -> TaskCompletion:
        completion = TaskCompletion(
            user_id=user_id,
            task_id=task_id,
            status=TaskStatus.PENDING,
            screenshot_file_id=screenshot_file_id,
            forwarded_from_chat_id=forwarded_from_chat_id,
            screenshots_count=screenshots_count
        )
        self.session.add(completion)
        await self.session.flush()
        await self.session.refresh(completion)
        return completion
    
    async def update_completion_status(self, completion_id: int, status: TaskStatus) -> TaskCompletion:
        result = await self.session.execute(
            select(TaskCompletion).where(TaskCompletion.id == completion_id)
        )
        completion = result.scalar_one_or_none()
        if completion:
            completion.status = status
            await self.session.flush()
            await self.session.refresh(completion)
        return completion
    
    async def get_all_tasks(self) -> List[Task]:
        result = await self.session.execute(
            select(Task).order_by(Task.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_completion_count(self, task_id: int) -> int:
        result = await self.session.execute(
            select(TaskCompletion).where(
                TaskCompletion.task_id == task_id,
                TaskCompletion.status == TaskStatus.APPROVED
            )
        )
        return len(list(result.scalars().all()))
    
    async def update_status_by_name(self, task_id: int, status: str) -> Task:
        task = await self.get_by_id(task_id)
        if task:
            task.status = TaskStatus(status)
            await self.session.flush()
            await self.session.refresh(task)
        return task
    
    async def delete(self, task_id: int):
        task = await self.get_by_id(task_id)
        if task:
            await self.session.delete(task)
            await self.session.flush()


class WithdrawalRepository:
    """Withdrawal repository for database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, withdrawal_id: int) -> Optional[Withdrawal]:
        result = await self.session.execute(
            select(Withdrawal).where(Withdrawal.id == withdrawal_id)
        )
        return result.scalar_one_or_none()
    
    async def get_pending_withdrawals(self) -> List[Withdrawal]:
        result = await self.session.execute(
            select(Withdrawal)
            .options(selectinload(Withdrawal.user))
            .where(Withdrawal.status == WithdrawalStatus.PENDING)
            .order_by(Withdrawal.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_user_withdrawals(self, user_id: int, limit: int = 20) -> List[Withdrawal]:
        result = await self.session.execute(
            select(Withdrawal)
            .where(Withdrawal.user_id == user_id)
            .order_by(Withdrawal.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def create(self, user_id: int, amount: float, wallet_address: str) -> Withdrawal:
        withdrawal = Withdrawal(
            user_id=user_id,
            amount=amount,
            wallet_address=wallet_address,
            status=WithdrawalStatus.PENDING
        )
        self.session.add(withdrawal)
        await self.session.flush()
        await self.session.refresh(withdrawal)
        return withdrawal
    
    async def update_status(
        self, 
        withdrawal_id: int, 
        status: WithdrawalStatus, 
        admin_comment: str = None,
        processed_by: int = None,
        transaction_hash: str = None
    ) -> Withdrawal:
        withdrawal = await self.get_by_id(withdrawal_id)
        if withdrawal:
            withdrawal.status = status
            if admin_comment:
                withdrawal.admin_comment = admin_comment
            if processed_by:
                withdrawal.processed_by = processed_by
                withdrawal.processed_at = datetime.utcnow()
            if transaction_hash:
                withdrawal.transaction_hash = transaction_hash
            await self.session.flush()
            await self.session.refresh(withdrawal)
        return withdrawal


class PromoCodeRepository:
    """Promo code repository for database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, promo_id: int) -> Optional[PromoCode]:
        result = await self.session.execute(
            select(PromoCode).where(PromoCode.id == promo_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_code(self, code: str) -> Optional[PromoCode]:
        result = await self.session.execute(
            select(PromoCode).where(PromoCode.code == code.upper())
        )
        return result.scalar_one_or_none()
    
    async def get_all(self) -> List[PromoCode]:
        result = await self.session.execute(
            select(PromoCode).order_by(PromoCode.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def create(self, code: str, reward_amount: float, max_uses: int, created_by: int = None) -> PromoCode:
        promo = PromoCode(
            code=code.upper(),
            reward_amount=reward_amount,
            max_uses=max_uses,
            current_uses=0,
            is_active=True,
            created_by=created_by
        )
        self.session.add(promo)
        await self.session.flush()
        await self.session.refresh(promo)
        return promo
    
    async def delete(self, promo_id: int) -> bool:
        promo = await self.get_by_id(promo_id)
        if promo:
            await self.session.delete(promo)
            await self.session.flush()
            return True
        return False
    
    async def use_promo_code(self, promo_id: int, user_id: int) -> PromoCode:
        promo = await self.get_by_id(promo_id)
        if promo:
            promo.current_uses += 1
            use = PromoCodeUse(promo_code_id=promo_id, user_id=user_id)
            self.session.add(use)
            await self.session.flush()
            await self.session.refresh(promo)
        return promo
    
    async def has_user_used(self, promo_id: int, user_id: int) -> bool:
        result = await self.session.execute(
            select(PromoCodeUse)
            .where(PromoCodeUse.promo_code_id == promo_id)
            .where(PromoCodeUse.user_id == user_id)
        )
        return result.scalar_one_or_none() is not None


class AdminLogRepository:
    """Admin log repository for database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, admin_id: int, action: str, target_type: str = None, target_id: int = None, details: str = None) -> AdminLog:
        log = AdminLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details
        )
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log
    
    async def get_by_admin(self, admin_id: int, limit: int = 50) -> List[AdminLog]:
        result = await self.session.execute(
            select(AdminLog)
            .where(AdminLog.admin_id == admin_id)
            .order_by(AdminLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class SponsorRepository:
    """Sponsor repository for database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, sponsor_id: int) -> Optional[Sponsor]:
        result = await self.session.execute(
            select(Sponsor).where(Sponsor.id == sponsor_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self) -> List[Sponsor]:
        result = await self.session.execute(
            select(Sponsor).order_by(Sponsor.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_active(self) -> List[Sponsor]:
        result = await self.session.execute(
            select(Sponsor).where(Sponsor.is_active == True)
        )
        return list(result.scalars().all())
    
    async def create(self, link: str, title: str = None) -> Sponsor:
        sponsor = Sponsor(link=link, title=title)
        self.session.add(sponsor)
        await self.session.flush()
        await self.session.refresh(sponsor)
        return sponsor
    
    async def delete(self, sponsor_id: int) -> bool:
        sponsor = await self.get_by_id(sponsor_id)
        if sponsor:
            await self.session.delete(sponsor)
            await self.session.flush()
            return True
        return False
    
    async def toggle_status(self, sponsor_id: int) -> Optional[Sponsor]:
        sponsor = await self.get_by_id(sponsor_id)
        if sponsor:
            sponsor.is_active = not sponsor.is_active
            await self.session.flush()
            await self.session.refresh(sponsor)
            return sponsor
        return None