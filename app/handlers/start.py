"""
Start command, language selection, settings, and main menu handler.
"""
import logging
from aiogram import Router, F, types, Bot
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
    
    # Проверяем подписку на спонсоров
    from app.database.repositories import SponsorRepository
    
    bot_check = Bot(token=config.BOT_TOKEN)
    
    try:
        async with db.async_session_maker() as sess:
            sponsor_repo = SponsorRepository(sess)
            active_sponsors = await sponsor_repo.get_active()
        
        if active_sponsors:
            is_subscribed = True
            user_id = message.from_user.id
            
            for sponsor in active_sponsors:
                username = sponsor.link.replace("https://t.me/", "").replace("@", "")
                try:
                    member = await bot_check.get_chat_member(chat_id=username, user_id=user_id)
                    if member.status in ['left', 'kicked']:
                        is_subscribed = False
                        break
                except Exception:
                    is_subscribed = False
                    break
            
            if not is_subscribed:
                # Отправляем требование подписаться
                keyboard = []
                text = "🛑 Чтобы пользоваться ботом, необходимо подписаться на наших спонсоров:\n\n"
                
                for i, sponsor in enumerate(active_sponsors, 1):
                    title = sponsor.title or sponsor.link
                    text += f"{i}. {title}\n"
                    keyboard.append([types.InlineKeyboardButton(text=f"➤ Подписаться {i}", url=sponsor.link)])
                
                keyboard.append([types.InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")])
                reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
                
                await message.answer(text, reply_markup=reply_markup)
                return
    finally:
        await bot_check.session.close()
    
    # Если подписан или спонсоров нет - показываем выбор языка
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


@router.callback_query(F.data == "check_subscription")
async def handle_check_subscription(callback: types.CallbackQuery):
    """Обработчик кнопки проверки подписки на спонсоров."""
    from app.database.repositories import UserRepository, SponsorRepository
    from app.config_reader import settings
    from aiogram import Bot
    
    user_id = callback.from_user.id
    
    # Создаем временного бота для проверки
    bot = Bot(token=settings.BOT_TOKEN)
    
    try:
        async with db.async_session_maker() as session:
            sponsor_repo = SponsorRepository(session)
            active_sponsors = await sponsor_repo.get_active()
        
        if not active_sponsors:
            await callback.answer("Подписка не требуется!", show_alert=True)
            return
        
        is_subscribed = True
        for sponsor in active_sponsors:
            username = sponsor.link.replace("https://t.me/", "").replace("@", "")
            try:
                member = await bot.get_chat_member(chat_id=username, user_id=user_id)
                if member.status in ['left', 'kicked']:
                    is_subscribed = False
                    break
            except Exception:
                is_subscribed = False
                break
        
        if is_subscribed:
            await callback.answer("✅ Подписка подтверждена! Добро пожаловать.", show_alert=True)
            # Очищаем сообщение с требованием подписки
            try:
                await callback.message.delete()
            except:
                pass
            # Показываем главное меню
            async with db.async_session_maker() as session:
                user_repo = UserRepository(session)
                db_user = await user_repo.get_by_telegram_id(user_id)
                lang = db_user.language_code if db_user else "en"
                is_admin = user_id in config.ADMIN_IDS
                await callback.message.answer(
                    "✅ Вы подписались на всех спонсоров. Теперь вы можете пользоваться ботом!",
                    reply_markup=get_main_menu_keyboard(lang, is_admin)
                )
        else:
            await callback.answer("❌ Вы еще не подписались на все каналы. Пожалуйста, подпишитесь и нажмите кнопку снова.", show_alert=True)
            
    finally:
        await bot.session.close()


@router.callback_query(F.data == "help")
async def handle_help(callback: types.CallbackQuery):
    from app.database.repositories import UserRepository
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    async with db.async_session_maker() as session:
        user_repo = UserRepository(session)
        db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
        
        lang = get_lang(db_user)
        
        if lang == "ru":
            text = (
                "🆘 **Помощь**\n\n"
                "📋 **Как работать с ботом:**\n"
                "1. Нажмите 📋 Задания, чтобы выбрать категорию\n"
                "2. Выберите задание и выполните условия\n"
                "3. Для ручной проверки отправьте скриншоты или перешлите сообщение\n"
                "4. Ожидайте подтверждения от администратора\n\n"
                "💰 **Баланс:**\n"
                "- Зарабатывайте TON, выполняя задания\n"
                "- Минимальный вывод: 1 TON\n"
                "- Вывод средств в разделе 💸 Вывести\n\n"
                "👥 **Рефералы:**\n"
                "- Приглашайте друзей и получайте бонусы\n"
                "- Ваша реферальная ссылка в разделе 👥 Рефералы\n\n"
                "❓ **Вопросы?**\n"
                "Свяжитесь с поддержкой: @support_username"
            )
        else:
            text = (
                "🆘 **Help**\n\n"
                "📋 **How to use the bot:**\n"
                "1. Tap 📋 Tasks to select a category\n"
                "2. Choose a task and complete the requirements\n"
                "3. For manual check, send screenshots or forward a message\n"
                "4. Wait for admin approval\n\n"
                "💰 **Balance:**\n"
                "- Earn TON by completing tasks\n"
                "- Minimum withdrawal: 1 TON\n"
                "- Withdraw funds in 💸 Withdraw section\n\n"
                "👥 **Referrals:**\n"
                "- Invite friends and get bonuses\n"
                "- Your referral link in 👥 Referrals section\n\n"
                "❓ **Questions?**\n"
                "Contact support: @support_username"
            )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 Back", callback_data="main_menu")
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer()