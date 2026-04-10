"""
Withdrawal system handlers.
"""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database.repositories import WithdrawalRepository, UserRepository
from app.models import WithdrawalStatus
from app.keyboards import get_withdraw_keyboard, get_back_keyboard, get_confirm_keyboard
from app.config import config
from app.utils import format_balance, validate_wallet_address

router = Router()


class WithdrawStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_wallet = State()
    waiting_for_confirmation = State()


def get_lang(user) -> str:
    lang = getattr(user, "language_code", "en") or "en"
    return lang if lang in ("ru", "en") else "en"


@router.callback_query(F.data == "withdraw")
async def handle_withdraw_menu(callback: types.CallbackQuery, session, user):
    lang = get_lang(user)
    if lang == "ru":
        text = (
            f"💸 Вывод средств\n\n"
            f"📊 Доступно: {format_balance(user.balance)}\n"
            f"❄️ Заморожено: {format_balance(user.frozen_balance)}\n\n"
            f"⚠️ Минимальный вывод: {config.MIN_WITHDRAWAL_AMOUNT} TON"
        )
    else:
        text = (
            f"💸 Withdrawal\n\n"
            f"📊 Available: {format_balance(user.balance)}\n"
            f"❄️ Frozen: {format_balance(user.frozen_balance)}\n\n"
            f"⚠️ Minimum withdrawal: {config.MIN_WITHDRAWAL_AMOUNT} TON"
        )
    await callback.message.edit_text(text, reply_markup=get_withdraw_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "withdraw_create")
async def handle_withdraw_create(callback: types.CallbackQuery, state: FSMContext, user):
    lang = get_lang(user)
    if user.balance < config.MIN_WITHDRAWAL_AMOUNT:
        msg = (f"❌ Недостаточно средств. Минимум {config.MIN_WITHDRAWAL_AMOUNT} TON."
               if lang == "ru" else
               f"❌ Insufficient balance. Minimum {config.MIN_WITHDRAWAL_AMOUNT} TON.")
        await callback.answer(msg, show_alert=True)
        return
    if lang == "ru":
        text = (f"💸 Создание заявки\n\n📊 Баланс: {format_balance(user.balance)}\n"
                f"⚠️ Минимум: {config.MIN_WITHDRAWAL_AMOUNT} TON\n\nВведите сумму:")
    else:
        text = (f"💸 Create Withdrawal\n\n📊 Balance: {format_balance(user.balance)}\n"
                f"⚠️ Minimum: {config.MIN_WITHDRAWAL_AMOUNT} TON\n\nEnter amount:")
    await callback.message.edit_text(text, reply_markup=get_back_keyboard("withdraw", lang))
    await state.set_state(WithdrawStates.waiting_for_amount)
    await callback.answer()


@router.message(WithdrawStates.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext, user):
    lang = get_lang(user)
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число." if lang == "ru" else "❌ Enter a number.")
        return
    if amount < config.MIN_WITHDRAWAL_AMOUNT:
        await message.answer(f"❌ Минимум {config.MIN_WITHDRAWAL_AMOUNT} TON." if lang == "ru"
                             else f"❌ Minimum {config.MIN_WITHDRAWAL_AMOUNT} TON.")
        return
    if amount > user.balance:
        await message.answer(f"❌ Недостаточно средств." if lang == "ru" else f"❌ Insufficient balance.")
        return
    await state.update_data(withdraw_amount=amount)
    text = (f"✅ Сумма: {format_balance(amount)}\n\nВведите адрес TON-кошелька:" if lang == "ru"
            else f"✅ Amount: {format_balance(amount)}\n\nEnter your TON wallet address:")
    await message.answer(text, reply_markup=get_back_keyboard("withdraw", lang))
    await state.set_state(WithdrawStates.waiting_for_wallet)


@router.message(WithdrawStates.waiting_for_wallet)
async def process_withdraw_wallet(message: types.Message, state: FSMContext, user):
    lang = get_lang(user)
    wallet = message.text.strip()
    if not validate_wallet_address(wallet):
        await message.answer("❌ Неверный адрес (UQ/EQ)." if lang == "ru" else "❌ Invalid address (UQ/EQ).")
        return
    data = await state.update_data(withdraw_wallet=wallet)
    amount = data.get("withdraw_amount", 0)
    if lang == "ru":
        text = (f"💸 Подтвердите вывод\n\n💰 Сумма: {format_balance(amount)}\n"
                f"🏦 Кошелёк: <code>{wallet}</code>\n\nПодтвердить?")
    else:
        text = (f"💸 Confirm Withdrawal\n\n💰 Amount: {format_balance(amount)}\n"
                f"🏦 Wallet: <code>{wallet}</code>\n\nConfirm?")
    await message.answer(text, reply_markup=get_confirm_keyboard("withdraw_confirm", "withdraw_cancel", lang))
    await state.set_state(WithdrawStates.waiting_for_confirmation)


@router.callback_query(F.data == "withdraw_confirm")
async def confirm_withdrawal(callback: types.CallbackQuery, state: FSMContext, session, user):
    lang = get_lang(user)
    data = await state.get_data()
    amount = data.get("withdraw_amount", 0)
    wallet = data.get("withdraw_wallet", "")
    if not amount or not wallet:
        await callback.answer("❌ Error.", show_alert=True)
        await state.clear()
        return
    user_repo = UserRepository(session)
    await user_repo.deduct_balance(user.id, amount)
    withdraw_repo = WithdrawalRepository(session)
    withdrawal = await withdraw_repo.create(user_id=user.id, amount=amount, wallet_address=wallet)
    await state.clear()
    if lang == "ru":
        text = (f"✅ Заявка создана!\n\n📋 #{withdrawal.id}\n"
                f"💰 {format_balance(amount)}\n🏦 <code>{wallet}</code>\n\n⏳ Ожидайте.")
    else:
        text = (f"✅ Request created!\n\n📋 #{withdrawal.id}\n"
                f"💰 {format_balance(amount)}\n🏦 <code>{wallet}</code>\n\n⏳ Please wait.")
    await callback.message.edit_text(text, reply_markup=get_back_keyboard("withdraw", lang))
    await callback.answer()


@router.callback_query(F.data == "withdraw_cancel")
async def cancel_withdrawal(callback: types.CallbackQuery, state: FSMContext, session, user):
    lang = get_lang(user)
    await state.clear()
    await callback.message.edit_text(
        "❌ Вывод отменён." if lang == "ru" else "❌ Withdrawal cancelled.",
        reply_markup=get_withdraw_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "withdraw_history")
async def handle_withdraw_history(callback: types.CallbackQuery, session, user):
    lang = get_lang(user)
    withdraw_repo = WithdrawalRepository(session)
    withdrawals = await withdraw_repo.get_user_withdrawals(user.id)
    if not withdrawals:
        text = "📜 История выводов\n\nПусто." if lang == "ru" else "📜 History\n\nNo withdrawals yet."
        await callback.message.edit_text(text, reply_markup=get_withdraw_keyboard(lang))
        await callback.answer()
        return
    text = "📜 История выводов\n\n" if lang == "ru" else "📜 History\n\n"
    for w in withdrawals[:10]:
        emoji = {"PENDING": "⏳", "PROCESSING": "⚙️", "COMPLETED": "✅", "REJECTED": "❌"}.get(
            w.status.name if hasattr(w.status, "name") else str(w.status), "❓"
        )
        text += f"{emoji} #{w.id} — {format_balance(w.amount)}\n"
    await callback.message.edit_text(text, reply_markup=get_back_keyboard("withdraw", lang))
    await callback.answer()
