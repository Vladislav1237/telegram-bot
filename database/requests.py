from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import (
    User,
    Task,
    UserTask,
    Withdrawal,
    PromoCode,
    SubscriptionReward,
    TaskStatus,
    WithdrawalStatus,
)


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, user_id: int) -> User:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(id=user_id)
            self.session.add(user)
            await self.session.flush()
        return user

    async def get(self, user_id: int) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def add_balance(self, user_id: int, amount: float) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(
                balance=User.balance + amount,
                total_earned=User.total_earned + amount
            )
        )

    async def add_frozen_balance(self, user_id: int, amount: float) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(
                frozen_balance=User.frozen_balance + amount
            )
        )

    async def set_referrer(self, user_id: int, referrer_id: int) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(referrer_id=referrer_id)
        )
        await self.session.execute(
            update(User).where(User.id == referrer_id).values(
                total_referrals=User.total_referrals + 1
            )
        )

    async def update_language(self, user_id: int, language: str) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(language=language)
        )


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_tasks(self) -> List[Task]:
        result = await self.session.execute(
            select(Task).where(Task.is_active == True)
        )
        return list(result.scalars().all())

    async def get_task(self, task_id: int) -> Optional[Task]:
        result = await self.session.execute(
            select(Task).where(Task.id == task_id)
        )
        return result.scalar_one_or_none()

    async def create_task(
        self, title: str, description: str, reward: float
    ) -> Task:
        task = Task(title=title, description=description, reward=reward)
        self.session.add(task)
        await self.session.flush()
        return task

    async def create_user_task(
        self, user_id: int, task_id: int, screenshot_id: str
    ) -> UserTask:
        user_task = UserTask(
            user_id=user_id,
            task_id=task_id,
            screenshot_id=screenshot_id,
            status=TaskStatus.PENDING.value,
        )
        self.session.add(user_task)
        await self.session.flush()
        return user_task

    async def get_pending_tasks(self) -> List[UserTask]:
        result = await self.session.execute(
            select(UserTask, Task, User)
            .join(Task, UserTask.task_id == Task.id)
            .join(User, UserTask.user_id == User.id)
            .where(UserTask.status == TaskStatus.PENDING.value)
        )
        return list(result.all())

    async def update_user_task_status(
        self, user_task_id: int, status: str
    ) -> None:
        await self.session.execute(
            update(UserTask)
            .where(UserTask.id == user_task_id)
            .values(status=status, updated_at=datetime.now())
        )


class WithdrawalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, user_id: int, amount: float, address: str
    ) -> Withdrawal:
        withdrawal = Withdrawal(
            user_id=user_id,
            amount=amount,
            address=address,
            status=WithdrawalStatus.PENDING.value,
        )
        self.session.add(withdrawal)
        await self.session.flush()
        return withdrawal

    async def get_pending(self) -> List[Withdrawal]:
        result = await self.session.execute(
            select(Withdrawal, User)
            .join(User, Withdrawal.user_id == User.id)
            .where(Withdrawal.status == WithdrawalStatus.PENDING.value)
        )
        return list(result.all())

    async def get_user_withdrawals(self, user_id: int) -> List[Withdrawal]:
        result = await self.session.execute(
            select(Withdrawal)
            .where(Withdrawal.user_id == user_id)
            .order_by(Withdrawal.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self, withdrawal_id: int, status: str
    ) -> None:
        await self.session.execute(
            update(Withdrawal)
            .where(Withdrawal.id == withdrawal_id)
            .values(status=status, processed_at=datetime.now())
        )


class PromoCodeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, code: str) -> Optional[PromoCode]:
        result = await self.session.execute(
            select(PromoCode).where(
                PromoCode.code == code,
                PromoCode.uses_left > 0
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, code: str, reward: float, uses: int, creator_id: int
    ) -> PromoCode:
        promo = PromoCode(
            code=code,
            reward=reward,
            uses_left=uses,
            created_by=creator_id,
        )
        self.session.add(promo)
        await self.session.flush()
        return promo

    async def use_code(self, code: str) -> None:
        await self.session.execute(
            update(PromoCode)
            .where(PromoCode.code == code)
            .values(uses_left=PromoCode.uses_left - 1)
        )


class SubscriptionRewardRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_frozen_reward(
        self, user_id: int, amount: float
    ) -> SubscriptionReward:
        reward = SubscriptionReward(
            user_id=user_id,
            amount=amount,
            status="frozen",
            unfreeze_at=datetime.now() + timedelta(hours=24),
        )
        self.session.add(reward)
        await self.session.flush()
        return reward

    async def get_ready_to_unfreeze(self) -> List[SubscriptionReward]:
        result = await self.session.execute(
            select(SubscriptionReward)
            .where(
                SubscriptionReward.status == "frozen",
                SubscriptionReward.unfreeze_at <= datetime.now()
            )
        )
        return list(result.scalars().all())

    async def unfreeze(self, reward_id: int) -> None:
        await self.session.execute(
            update(SubscriptionReward)
            .where(SubscriptionReward.id == reward_id)
            .values(status="paid", processed_at=datetime.now())
        )

    async def delete(self, reward_id: int) -> None:
        await self.session.execute(
            delete(SubscriptionReward).where(SubscriptionReward.id == reward_id)
        )
