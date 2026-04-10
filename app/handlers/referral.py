"""
Referral system handlers.
"""
from aiogram import Router, F, types, Bot

from app.database.repositories import UserRepository
from app.keyboards import get_back_keyboard
from app.utils import generate_referral_link, format_balance

router = Router()


@router.callback_query(F.data == "referrals")
async def handle_referrals(
    callback: types.CallbackQuery,
    session,
    user,
):
    """Show referral information and link."""
    bot: Bot = callback.bot
    bot_info = await bot.get_me()

    referral_link = generate_referral_link(bot_info.username, user.id)

    user_repo = UserRepository(session)
    referral_count = await user_repo.get_referral_count(user.id)

    total_earned = referral_count * 0.025
    lang = getattr(user, "language_code", "en") or "en"

    if lang == "ru":
        text = (
            f"👥 Реферальная программа\n\n"
            f"📊 Ваши рефералы: {referral_count}\n"
            f"💰 Награда за реферала: 0.025 TON\n"
            f"💵 Всего заработано: {format_balance(total_earned)}\n\n"
            f"🔗 Ваша реферальная ссылка:\n"
            f"<code>{referral_link}</code>\n\n"
            f"💡 Поделитесь ссылкой с друзьями!\n"
            f"Когда они присоединятся, вы получите 0.025 TON."
        )
    else:
        text = (
            f"👥 Referral Program\n\n"
            f"📊 Your referrals: {referral_count}\n"
            f"💰 Reward per referral: 0.025 TON\n"
            f"💵 Total earned: {format_balance(total_earned)}\n\n"
            f"🔗 Your referral link:\n"
            f"<code>{referral_link}</code>\n\n"
            f"💡 Share this link with friends!\n"
            f"When they join, you'll receive 0.025 TON."
        )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📤 Поделиться" if lang == "ru" else "📤 Share Link",
        url=f"https://t.me/share/url?url={referral_link}&text={'Присоединяйся!' if lang == 'ru' else 'Join me!'}",
    )
    builder.button(
        text="🔙 Назад" if lang == "ru" else "🔙 Back",
        callback_data="main_menu",
    )
    builder.adjust(1, 1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
    )
    await callback.answer()
