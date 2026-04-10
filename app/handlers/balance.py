"""
Balance and economy handlers.
"""
from aiogram import Router, F, types

from app.database.repositories import UserRepository
from app.keyboards import get_back_keyboard
from app.utils import format_balance
from app.config import config

router = Router()


@router.callback_query(F.data == "balance")
async def handle_balance(
    callback: types.CallbackQuery,
    session,
    user,
):
    """Show user balance information."""
    total = user.balance + user.frozen_balance

    user_repo = UserRepository(session)
    referral_count = await user_repo.get_referral_count(user.id)

    lang = getattr(user, "language_code", "en") or "en"

    if lang == "ru":
        text = (
            f"💰 Информация о балансе\n\n"
            f"📊 Доступно: {format_balance(user.balance)}\n"
            f"❄️ Заморожено: {format_balance(user.frozen_balance)}\n"
            f"💵 Всего: {format_balance(total)}\n\n"
        )
        if user.is_subscribed:
            text += "✅ Подписка: Активна\n"
        else:
            text += "❌ Подписка: Неактивна\n"
            text += "💡 Подпишитесь для ежедневных наград!\n"

        if referral_count > 0:
            text += f"\n👥 У вас {referral_count} рефералов\n"
            text += f"💰 Заработано с рефералов: {format_balance(referral_count * 0.025)}\n"
    else:
        text = (
            f"💰 Balance Information\n\n"
            f"📊 Available: {format_balance(user.balance)}\n"
            f"❄️ Frozen: {format_balance(user.frozen_balance)}\n"
            f"💵 Total: {format_balance(total)}\n\n"
        )
        if user.is_subscribed:
            text += "✅ Subscription: Active\n"
        else:
            text += "❌ Subscription: Inactive\n"
            text += "💡 Subscribe to earn daily rewards!\n"

        if referral_count > 0:
            text += f"\n👥 You have {referral_count} referrals\n"
            text += f"💰 Earned from referrals: {format_balance(referral_count * 0.025)}\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "claim_reward")
async def handle_claim_reward(
    callback: types.CallbackQuery,
    session,
    user,
):
    """Claim daily subscription reward."""
    if not user.is_subscribed:
        await callback.answer("❌ Требуется активная подписка для получения наград.", show_alert=True)
        return

    reward_amount = 0.01
    user_repo = UserRepository(session)
    await user_repo.update_balance(user.id, reward_amount, freeze=True)  # Freeze 24h
    await user_repo.update_last_reward_claim(user.id)  # Add if missing

    lang = getattr(user, "language_code", "en") or "en"
    if lang == "ru":
        msg = f"✅ Награда получена!\n💰 Сумма: {format_balance(reward_amount)}\n⏰ Доступна через 24ч"
    else:
        msg = f"✅ Reward claimed!\n💰 Amount: {format_balance(reward_amount)}\n⏰ Available in 24h"

    await callback.message.answer(msg)
    await callback.answer()

