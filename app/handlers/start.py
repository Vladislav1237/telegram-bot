"""
Start command, language selection, settings, and main menu handler.
"""
import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from app.database.repositories import UserRepository
from app.database import db
from app.keyboards import get_main_menu_keyboard, get_language_keyboard, get_back_keyboard
from app.config import config

router = Router()
logger = logging.getLogger(__name__)


def get_lang(user) -> str:
    lang = getattr(user, "language_code", "en") or "en"
    return lang if lang in ("ru", "en") else "en"


@router.message()
async def handle_start(message: types.Message, session=None, user=None):
    if not message.text:
        return
    if not message.text.startswith("/start"):
        return
    
    logger.info(f"[START] === HANDLER CALLED === for {message.from_user.id}")
    logger.info(f"[START] message.text='{message.text}'")
    logger.info(f"[START] session={session is not None}, user={user}")
    
    try:
        kb = get_language_keyboard()
        logger.info(f"[START] Keyboard created: {kb}")
        
        sent = await message.answer(
            "🌐 Выберите язык / Choose language:",
            reply_markup=kb,
        )
        logger.info(f"[START] ANSWER SENT! message_id={sent.message_id}")
    except Exception as e:
        logger.error(f"[START] EXCEPTION: {type(e).__name__}: {e}", exc_info=True)
        try:
            await message.answer(f"Error: {e}")
        except Exception as e2:
            logger.error(f"[START] Failed to send error: {e2}")


@router.callback_query(F.data.startswith("lang_"))
async def handle_lang_select(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass
    
    lang = callback.data.split("_")[1]
    
    from app.database.repositories import UserRepository
    
    async with db.async_session_maker() as session:
        user_repo = UserRepository(session)
        db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
        if db_user:
            db_user.language_code = lang
            await session.commit()
    
    is_admin = callback.from_user.id in config.ADMIN_IDS
    
    welcome_ru = (
        f"👋 Добро пожаловать, {callback.from_user.first_name}!\n\n"
        "🎉 Вы успешно запустили бота.\n\n"
        "💡 Используйте меню:"
    )
    welcome_en = (
        f"👋 Welcome, {callback.from_user.first_name}!\n\n"
        "🎉 You've successfully started the bot.\n\n"
        "💡 Use the menu:"
    )
    
    welcome = welcome_ru if lang == "ru" else welcome_en
    
    try:
        await callback.message.edit_text("✅ Language set!")
    except TelegramBadRequest:
        pass
    
    try:
        await callback.message.answer(welcome, reply_markup=get_main_menu_keyboard(lang, is_admin))
    except TelegramBadRequest:
        pass
    
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "main_menu")
async def handle_main_menu(callback: types.CallbackQuery):
    from app.database.repositories import UserRepository
    
    async with db.async_session_maker() as session:
        user_repo = UserRepository(session)
        db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
        
        if not db_user:
            db_user = await user_repo.create(
                telegram_id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name,
                language_code=callback.from_user.language_code or "en",
            )
            await session.commit()
        
        lang = get_lang(db_user)
        referral_count = await user_repo.get_referral_count(db_user.id)
        
        text = (
            f"🏠 Main Menu\n\n"
            f"💰 Balance: {db_user.balance:.4f} TON\n"
            f"❄️ Frozen: {db_user.frozen_balance:.4f} TON\n"
            f"👥 Referrals: {referral_count}"
        )
        
        is_admin = callback.from_user.id in config.ADMIN_IDS
        await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(lang, is_admin))
        await callback.answer()


@router.callback_query(F.data == "settings")
async def handle_settings(callback: types.CallbackQuery):
    from app.database.repositories import UserRepository
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    async with db.async_session_maker() as session:
        user_repo = UserRepository(session)
        db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
        
        lang = get_lang(db_user)
        reg_date = db_user.created_at.strftime("%d.%m.%Y") if db_user.created_at else "—"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🇬🇧 English", callback_data="lang_en")
        builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
        builder.button(text="🔙 Back", callback_data="main_menu")
        builder.adjust(2, 1)
        
        text = (
            f"⚙️ Settings\n\n"
            f"🆔 Your ID: <code>{db_user.telegram_id}</code>\n"
            f"🌐 Language: {lang}\n"
            f"📅 Registered: {reg_date}"
        )
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()