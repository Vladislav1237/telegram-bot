"""
Promo code system handlers.
"""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database.repositories import PromoCodeRepository, UserRepository
from app.keyboards import get_back_keyboard
from app.utils import format_balance

router = Router()


class PromoStates(StatesGroup):
    waiting_for_code = State()


def get_lang(user) -> str:
    lang = getattr(user, "language_code", "en") or "en"
    return lang if lang in ("ru", "en") else "en"


@router.callback_query(F.data == "promo")
async def handle_promo_menu(
    callback: types.CallbackQuery,
    state: FSMContext,
    session,
    user,
):
    lang = get_lang(user)

    if lang == "ru":
        text = "🎁 Промокод\n\nВведите промокод для получения награды:"
    else:
        text = "🎁 Promo Code\n\nEnter your promo code to receive a reward:"

    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await state.set_state(PromoStates.waiting_for_code)
    await callback.answer()


@router.message(PromoStates.waiting_for_code)
async def process_promo_code(
    message: types.Message,
    state: FSMContext,
    session,
    user,
):
    from datetime import datetime

    lang = get_lang(user)
    code = message.text.strip().upper()

    if not code:
        await message.answer(
            "❌ Введите промокод." if lang == "ru" else "❌ Please enter a promo code."
        )
        return

    promo_repo = PromoCodeRepository(session)
    promo = await promo_repo.get_by_code(code)

    if not promo:
        await message.answer(
            "❌ Промокод не найден." if lang == "ru" else "❌ Invalid promo code.",
            reply_markup=get_back_keyboard(),
        )
        await state.clear()
        return

    if not promo.is_active:
        await message.answer(
            "❌ Промокод деактивирован." if lang == "ru" else "❌ Promo code deactivated.",
            reply_markup=get_back_keyboard(),
        )
        await state.clear()
        return

    if promo.expires_at and datetime.utcnow() > promo.expires_at:
        await message.answer(
            "❌ Промокод истёк." if lang == "ru" else "❌ Promo code expired.",
            reply_markup=get_back_keyboard(),
        )
        await state.clear()
        return

    if promo.current_uses >= promo.max_uses:
        await message.answer(
            "❌ Промокод исчерпан." if lang == "ru" else "❌ Promo code limit reached.",
            reply_markup=get_back_keyboard(),
        )
        await state.clear()
        return

    has_used = await promo_repo.has_user_used(promo.id, user.id)
    if has_used:
        await message.answer(
            "❌ Вы уже использовали этот промокод."
            if lang == "ru"
            else "❌ You already used this promo code.",
            reply_markup=get_back_keyboard(),
        )
        await state.clear()
        return

    user_repo = UserRepository(session)
    await user_repo.update_balance(user.id, promo.reward_amount, freeze=False)
    await promo_repo.use_promo_code(promo.id, user.id)

    await state.clear()

    if lang == "ru":
        text = (
            f"✅ Промокод активирован!\n\n"
            f"🎁 Награда: {format_balance(promo.reward_amount)}\n"
            f"💰 Новый баланс: {format_balance(user.balance + promo.reward_amount)}"
        )
    else:
        text = (
            f"✅ Promo code activated!\n\n"
            f"🎁 Reward: {format_balance(promo.reward_amount)}\n"
            f"💰 New balance: {format_balance(user.balance + promo.reward_amount)}"
        )

    await message.answer(text, reply_markup=get_back_keyboard())
