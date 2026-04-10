"""
Task system handlers.
- Admin creates tasks (subscribe/bots/groups/custom)
- Users browse tasks by category and complete them (click link to join)
"""
import logging
from datetime import datetime
from sqlalchemy import select, and_
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.repositories import TaskRepository, UserRepository, UserRepository
from app.models import TaskStatus, Task, TaskCompletion
from app.keyboards import get_tasks_keyboard, get_back_keyboard
from app.config import config

router = Router()


class AdminTaskStates(StatesGroup):
    waiting_category = State()
    waiting_link = State()
    waiting_description = State()
    waiting_reward = State()


class TaskUserStates(StatesGroup):
    waiting_screenshot = State()


def get_lang(user) -> str:
    lang = getattr(user, "language_code", "en") or "en"
    return lang if lang in ("ru", "en") else "en"


# ── User: tasks menu ────────────────────────────────────────────
@router.callback_query(F.data == "tasks")
async def handle_tasks_menu(
    callback: types.CallbackQuery,
    session,
    user,
):
    import logging
    logging.info(f"[TASKS] handle_tasks_menu called: callback.data={callback.data}")
    
    if not user:
        logging.error("[TASKS] User is None!")
        await callback.answer("⚠️ Error: Please restart bot with /start", show_alert=True)
        return
    
    try:
        lang = get_lang(user)
        logging.info(f"[TASKS] User lang: {lang}, user.telegram_id: {user.telegram_id}")

        if lang == "ru":
            text = (
                "📋 Задания\n\n"
                "Выполняй задания и зарабатывай TON!\n"
                "Выберите категорию:"
            )
        else:
            text = (
                "📋 Tasks\n\n"
                "Complete tasks and earn TON!\n"
                "Choose a category:"
            )

        await callback.message.edit_text(text, reply_markup=get_tasks_keyboard(lang))
        await callback.answer()
        logging.info("[TASKS] handle_tasks_menu completed successfully")
    except Exception as e:
        logging.error(f"[TASKS] Error in handle_tasks_menu: {e}", exc_info=True)
        await callback.answer(f"⚠️ Error: {str(e)[:50]}", show_alert=True)


# ── User: browse tasks by category ──────────────────────────────
@router.callback_query(F.data.startswith("tasks_cat_"))
async def handle_tasks_category(
    callback: types.CallbackQuery,
    session,
    user,
):
    import logging
    logging.info(f"[TASKS] handle_tasks_category called: callback.data={callback.data}")
    
    if not user:
        logging.error("[TASKS] User is None in handle_tasks_category!")
        await callback.answer("⚠️ Error: Please restart bot with /start", show_alert=True)
        return
    
    try:
        lang = get_lang(user)
        category = callback.data.replace("tasks_cat_", "")
        logging.info(f"[TASKS] Category: {category}, lang: {lang}")

        cat_names = {
            "subscribe": ("📢 Подписка", "📢 Subscribe"),
            "bots": ("🤖 Боты", "🤖 Bots"),
            "groups": ("👥 Группы", "👥 Groups"),
        }
        cat_name = cat_names.get(category, ("📋", "📋"))
        title = cat_name[0] if lang == "ru" else cat_name[1]

        task_repo = TaskRepository(session)
        
        result = await session.execute(
            select(Task)
            .where(Task.category == category)
            .where(Task.is_active == True)
            .where(Task.id.notin_(
                select(TaskCompletion.task_id).where(
                    and_(TaskCompletion.user_id == user.id, TaskCompletion.status.in_([TaskStatus.APPROVED, TaskStatus.PENDING]))
                )
            ))
            .order_by(Task.created_at.desc())
        )
        tasks = list(result.scalars().all())
        logging.info(f"[TASKS] Found {len(tasks)} tasks (excluding completed)")

        if not tasks:
            if lang == "ru":
                text = f"{title}\n\n✅ Все задания выполнены!"
            else:
                text = f"{title}\n\n✅ All tasks completed!"

            await callback.message.edit_text(
                text,
                reply_markup=get_back_keyboard("tasks", lang),
            )
            await callback.answer()
            return

        builder = InlineKeyboardBuilder()

        for task in tasks[:20]:
            label = f"{'➡️ '}{task.title[:40]} — {task.reward:.4f} TON"
            builder.button(text=label, callback_data=f"task_view:{task.id}")

        builder.button(
            text="🔙 Назад" if lang == "ru" else "🔙 Back",
            callback_data="tasks",
        )
        builder.adjust(1)

        if lang == "ru":
            text = f"{title}\n\nДоступные задания:"
        else:
            text = f"{title}\n\nAvailable tasks:"

        await callback.message.edit_text(text, reply_markup=builder.as_markup())
        await callback.answer()
        logging.info("[TASKS] handle_tasks_category completed")
    except Exception as e:
        logging.error(f"[TASKS] Error in handle_tasks_category: {e}", exc_info=True)
        await callback.answer(f"⚠️ Error: {str(e)[:50]}", show_alert=True)


# ── User: view single task ──────────────────────────────────────
@router.callback_query(F.data.startswith("task_view:"))
async def handle_task_view(
    callback: types.CallbackQuery,
    session,
    user,
    bot,
):
    if not user:
        await callback.answer("⚠️ Пожалуйста, перезапустите бота /start", show_alert=True)
        return
    
    lang = get_lang(user)
    task_id = int(callback.data.split(":")[1])

    task_repo = TaskRepository(session)
    task = await task_repo.get_by_id(task_id)

    if not task:
        await callback.answer("❌ Task not found", show_alert=True)
        return

    builder = InlineKeyboardBuilder()

    link = task.description or ""

    if link.startswith("https://"):
        btn_text = {
            "subscribe": "📢 Подписаться" if lang == "ru" else "📢 Subscribe",
            "bots": "🤖 Запустить бота" if lang == "ru" else "📢 Start Bot",
            "groups": "👥 Вступить в группу" if lang == "ru" else "📢 Join Group",
        }.get(task.category or "", "🔗 Перейти" if lang == "ru" else "🔗 Open")
        builder.button(text=btn_text, url=link)

    builder.button(
        text="🔄 Проверить" if lang == "ru" else "🔄 Check",
        callback_data=f"task_check:{task_id}",
    )
    
    # For manual tasks, show "Send Screenshot" button
    if task.check_type == "manual":
        builder.button(
            text="📸 Отправить скриншот" if lang == "ru" else "📸 Send Screenshot",
            callback_data=f"task_submit:{task_id}",
        )
    
    builder.button(
        text="🔙 Назад" if lang == "ru" else "🔙 Back",
        callback_data=f"tasks_cat_{task.category or 'subscribe'}",
    )
    builder.adjust(1)

    if lang == "ru":
        text = (
            f"📋 Задание #{task.id}\n\n"
            f"📝 {task.title}\n"
            f"💰 Награда: {task.reward:.4f} TON\n\n"
            f"1. Подпишитесь на канал/бота/группу\n"
            f"2. Нажмите «Проверить» для верификации\n"
            f"3. Если подписка есть - получите награду!"
        )
    else:
        text = (
            f"📋 Task #{task.id}\n\n"
            f"📝 {task.title}\n"
            f"💰 Reward: {task.reward:.4f} TON\n\n"
            f"1. Subscribe to channel/bot/group\n"
            f"2. Press «Check» for verification\n"
            f"3. If subscribed - get your reward!"
        )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ── User: check subscription ───────────────────────────────────
@router.callback_query(F.data.startswith("task_check:"))
async def handle_task_check(
    callback: types.CallbackQuery,
    session,
    user,
    bot,
):
    logging.info(f"[TASK_CHECK] callback.data={callback.data}")
    
    if not user:
        logging.error("[TASK_CHECK] User is None!")
        await callback.answer("⚠️ Пожалуйста, перезапустите бота /start", show_alert=True)
        return
    
    try:
        lang = get_lang(user)
        task_id = int(callback.data.split(":")[1])
        logging.info(f"[TASK_CHECK] task_id={task_id}, user_id={user.telegram_id}")

        task_repo = TaskRepository(session)
        user_repo = UserRepository(session)
        task = await task_repo.get_by_id(task_id)

        if not task:
            logging.error(f"[TASK_CHECK] Task not found: {task_id}")
            await callback.answer("❌ Task not found", show_alert=True)
            return

        logging.info(f"[TASK_CHECK] Task found: category={task.category}, chat_id={task.chat_id}, bot_username={task.bot_username}, check_type={task.check_type}")

        # Handle manual check type
        if task.check_type == "manual":
            existing = await task_repo.get_user_task_completion(user.id, task_id)
            
            if existing:
                if existing.status == TaskStatus.PENDING:
                    if lang == "ru":
                        msg = "⏳ Задание на проверке. Ожидайте."
                    else:
                        msg = "⏳ Task is under review. Please wait."
                    await callback.answer(msg, show_alert=True)
                elif existing.status == TaskStatus.APPROVED:
                    if lang == "ru":
                        msg = "✅ Вы уже получили награду!"
                    else:
                        msg = "✅ You already got the reward!"
                    await callback.answer(msg, show_alert=True)
                else:
                    await task_repo.update_completion_status(existing.id, TaskStatus.PENDING)
                    if lang == "ru":
                        msg = "📸 Скриншот отправлен на проверку!"
                    else:
                        msg = "📸 Screenshot submitted for review!"
                    await callback.answer(msg, show_alert=True)
            else:
                await task_repo.create_completion(user_id=user.id, task_id=task_id)
                if lang == "ru":
                    msg = "📸 Задание отправлено на ручную проверку!\n⏳ Ожидайте подтверждения админа."
                else:
                    msg = "📸 Task submitted for manual review!\n⏳ Wait for admin confirmation."
                await callback.answer(msg, show_alert=True)
            return

        try:
            chat_id = task.chat_id
            bot_username = task.bot_username
            
            if not chat_id and task.description and task.description.startswith("https://t.me/"):
                chat_id = task.description.replace("https://t.me/", "")
            
            if not bot_username and task.description and task.description.startswith("https://t.me/"):
                bot_username = task.description.replace("https://t.me/", "").replace("@", "")

            logging.info(f"[TASK_CHECK] Using: chat_id={chat_id}, bot_username={bot_username}, category={task.category}")
            
            is_subscribed = False
            
            # Try Pyrogram first (works without being admin)
            if config.TELETHON_API_ID and config.TELETHON_API_HASH:
                try:
                    if task.category == "subscribe" and chat_id:
                        is_subscribed = await pyrogram_check_subscription(user.telegram_id, chat_id)
                        logging.info(f"[TASK_CHECK] Pyrogram subscribe check: {chat_id}, subscribed={is_subscribed}")
                    elif task.category == "bots" and bot_username:
                        is_subscribed = await pyrogram_check_subscription(user.telegram_id, bot_username)
                        logging.info(f"[TASK_CHECK] Pyrogram bot check: {bot_username}, subscribed={is_subscribed}")
                    elif task.category == "groups" and chat_id:
                        is_subscribed = await pyrogram_check_subscription(user.telegram_id, chat_id)
                        logging.info(f"[TASK_CHECK] Pyrogram group check: {chat_id}, subscribed={is_subscribed}")
                except Exception as e:
                    logging.info(f"[CHECK] Pyrogram error: {e}")
            
            # Fallback to aiogram if Telethon not configured
            if not is_subscribed and not config.TELETHON_API_ID:
                if task.category == "subscribe" and chat_id:
                    try:
                        target = chat_id if chat_id.startswith("@") else f"@{chat_id.replace('@', '')}"
                        chat_obj = await bot.get_chat(target)
                        member = await bot.get_chat_member(chat_obj.id, user.telegram_id)
                        is_subscribed = member.status in ["member", "administrator", "creator"]
                        logging.info(f"[TASK_CHECK] AIogram subscribe check: {target}, status={member.status}, subscribed={is_subscribed}")
                    except Exception as e:
                        logging.info(f"[CHECK] AIogram error: {e}")
                        is_subscribed = False
                elif task.category == "bots" and bot_username:
                    try:
                        target = bot_username if bot_username.startswith("@") else f"@{bot_username}"
                        chat_obj = await bot.get_chat(target)
                        member = await bot.get_chat_member(chat_obj.id, user.telegram_id)
                        is_subscribed = member.status in ["member", "administrator", "creator"]
                        logging.info(f"[TASK_CHECK] AIogram bot check: {target}, status={member.status}, subscribed={is_subscribed}")
                    except Exception as e:
                        logging.info(f"[CHECK] AIogram error: {e}")
                        is_subscribed = False
                elif task.category == "groups" and chat_id:
                    try:
                        target = chat_id if chat_id.startswith("@") else f"@{chat_id.replace('@', '')}"
                        chat_obj = await bot.get_chat(target)
                        member = await bot.get_chat_member(chat_obj.id, user.telegram_id)
                        is_subscribed = member.status in ["member", "administrator", "creator", "restricted"]
                        logging.info(f"[TASK_CHECK] AIogram group check: {target}, status={member.status}, subscribed={is_subscribed}")
                    except Exception as e:
                        logging.info(f"[CHECK] AIogram error: {e}")
                        is_subscribed = False
            else:
                logging.info(f"[TASK_CHECK] No chat_id or bot_username to check")
                is_subscribed = False
        except Exception as e:
            logging.error(f"[TASK_CHECK] Error during check: {e}", exc_info=True)
            if lang == "ru":
                await callback.answer(f"⚠️ Ошибка проверки: {str(e)[:50]}", show_alert=True)
            else:
                await callback.answer(f"⚠️ Check error: {str(e)[:50]}", show_alert=True)
            return

        existing = await task_repo.get_user_task_completion(user.id, task_id)
        
        if is_subscribed:
            if existing and existing.status == TaskStatus.APPROVED:
                time_since = (datetime.utcnow() - existing.created_at).total_seconds()
                
                if time_since < 86400:
                    if lang == "ru":
                        msg = "✅ Награда заморожена! Через 24ч получите на баланс."
                    else:
                        msg = "✅ Reward frozen! After 24h it will be added to your balance."
                    await callback.answer(msg, show_alert=True)
                    return
                else:
                    await user_repo.update_balance(user.id, task.reward, freeze=False)
                    if lang == "ru":
                        text = (
                            f"⏰ 24 часа прошло!\n\n"
                            f"✅ Награда {task.reward:.4f} TON разморожена и добавлена на баланс!\n"
                            f"💵 Баланс: {user.balance:.4f} TON"
                        )
                    else:
                        text = (
                            f"⏰ 24 hours passed!\n\n"
                            f"✅ Reward {task.reward:.4f} TON unfrozen and added to balance!\n"
                            f"💵 Balance: {user.balance:.4f} TON"
                        )
                    builder = InlineKeyboardBuilder()
                    builder.button(
                        text="📋 К следующему заданию" if lang == "ru" else "📋 Next Task",
                        callback_data="tasks",
                    )
                    builder.adjust(1)
                    await callback.message.edit_text(text, reply_markup=builder.as_markup())
                    await callback.answer()
                    return
            
            await user_repo.update_balance(user.id, task.reward, freeze=True)
            
            completion = await task_repo.create_completion(user_id=user.id, task_id=task_id)
            await task_repo.update_completion_status(completion.id, TaskStatus.APPROVED)

            if lang == "ru":
                text = (
                    f"✅ ПОЗДРАВЛЯЕМ!\n\n"
                    f"💰 Награда: {task.reward:.4f} TON\n"
                    f"⏳ Награда заморожена на 24 часа\n"
                    f"💵 Заморожено: {user.frozen_balance:.4f} TON\n\n"
                    f"⚠️ Не отписывайтесь в течение 24ч!"
                )
            else:
                text = (
                    f"✅ CONGRATULATIONS!\n\n"
                    f"💰 Reward: {task.reward:.4f} TON\n"
                    f"⏳ Reward frozen for 24 hours\n"
                    f"💵 Frozen: {user.frozen_balance:.4f} TON\n\n"
                    f"⚠️ Don't unsubscribe within 24h!"
                )
            
            builder = InlineKeyboardBuilder()
            builder.button(
                text="📋 К следующему заданию" if lang == "ru" else "📋 Next Task",
                callback_data="tasks",
            )
            builder.button(
                text="🔙 Назад" if lang == "ru" else "🔙 Back",
                callback_data=f"tasks_cat_{task.category or 'subscribe'}",
            )
            builder.adjust(1)
            
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
            logging.info(f"[TASK_CHECK] Reward frozen: {task.reward}")
        else:
            if existing and existing.status == TaskStatus.APPROVED:
                time_since = (datetime.utcnow() - existing.created_at).total_seconds()
                
                if time_since < 86400:
                    await user_repo.deduct_balance(user.id, task.reward)
                    user.violation_count = getattr(user, 'violation_count', 0) + 1
                    await session.flush()
                    
                    violation_count = getattr(user, 'violation_count', 0)
                    
                    if lang == "ru":
                        msg = f"❌ ВЫ ОТПИСАЛИСЬ! Награда снята.\n⚠️ Нарушений: {violation_count}/3"
                    else:
                        msg = f"❌ YOU UNSUBSCRIBED! Reward removed.\n⚠️ Violations: {violation_count}/3"
                    
                    if violation_count >= 3:
                        commission = task.reward * 0.2
                        if lang == "ru":
                            msg += f"\n💸 Комиссия 20%: {commission:.4f} TON"
                        else:
                            msg += f"\n💸 20% commission: {commission:.4f} TON"
                    
                    await task_repo.update_completion_status(existing.id, TaskStatus.REJECTED)
                    await callback.answer(msg, show_alert=True)
                else:
                    if lang == "ru":
                        msg = "⏰ 24 часа прошло! Можете выполнить задание снова."
                    else:
                        msg = "⏰ 24h passed! You can do the task again."
                    await task_repo.update_completion_status(existing.id, TaskStatus.REJECTED)
                    await callback.answer(msg, show_alert=True)
            elif existing:
                if lang == "ru":
                    msg = "⚠️ Вы уже проверяли. Подпишитесь и нажмите «Проверить»."
                else:
                    msg = "⚠️ You already checked. Subscribe and press «Check»."
                await callback.answer(msg, show_alert=True)
            else:
                if lang == "ru":
                    msg = "❌ Вы не подписаны! Сначала подпишитесь."
                else:
                    msg = "❌ Not subscribed! Subscribe first."
                await callback.answer(msg, show_alert=True)

        await callback.answer()
    except Exception as e:
        logging.error(f"[TASK_CHECK] Fatal error: {e}", exc_info=True)
        await callback.answer(f"⚠️ Error: {str(e)[:100]}", show_alert=True)


# ── User: submit screenshot for manual task ─────────────────────────
@router.callback_query(F.data.startswith("task_submit:"))
async def handle_task_submit(callback: types.CallbackQuery, session, user, state: FSMContext):
    logging.info(f"[TASK_SUBMIT] User {callback.from_user.id} clicked submit for task")
    lang = get_lang(user)
    task_id = int(callback.data.split(":")[1])
    
    task_repo = TaskRepository(session)
    task = await task_repo.get_by_id(task_id)
    
    if not task:
        await callback.answer("❌ Task not found", show_alert=True)
        return
    
    # Check if user already completed
    existing = await task_repo.get_user_task_completion(user.id, task_id)
    if existing:
        msg = "❌ Вы уже выполнили это задание." if lang == "ru" else "❌ You already completed this task."
        await callback.answer(msg, show_alert=True)
        return
    
    # Ask for screenshot
    await state.set_state(TaskUserStates.waiting_screenshot)
    await state.update_data(submit_task_id=task_id)
    logging.info(f"[TASK_SUBMIT] State set, task_id={task_id}")
    
    prompt = "📸 Отправьте скриншот выполненного задания:" if lang == "ru" else "📸 Send a screenshot of the completed task:"
    await callback.message.edit_text(prompt)
    await callback.answer()


# ── Handle screenshot for manual task ─────────────────────────────
@router.message(TaskUserStates.waiting_screenshot)
async def handle_manual_screenshot(message: types.Message, session, user, state: FSMContext):
    logging.info(f"[SCREENSHOT] Received from user {message.from_user.id}")
    logging.info(f"[SCREENSHOT] message.photo = {message.photo}")
    logging.info(f"[SCREENSHOT] message.content_type = {message.content_type}")
    
    try:
        # Check if it's a photo
        if not message.photo:
            logging.info("[SCREENSHOT] No photo in message")
            lang = get_lang(user)
            await message.answer("📸 Пожалуйста, отправьте фото/скриншот." if lang == "ru" else "📸 Please send a photo/screenshot.")
            return
        
        lang = get_lang(user)
        
        data = await state.get_data()
        task_id = data.get("submit_task_id")
        logging.info(f"[SCREENSHOT] task_id from state: {task_id}")
        
        if not task_id:
            logging.warning("[SCREENSHOT] No task_id in state!")
            await message.answer("❌ Error. Try again." if lang == "ru" else "❌ Error. Try again.")
            await state.clear()
            return
        
        task_repo = TaskRepository(session)
        task = await task_repo.get_by_id(task_id)
        
        if not task:
            await message.answer("❌ Task not found" if lang == "ru" else "❌ Task not found")
            await state.clear()
            return
        
        # Get photo file_id
        photo_file_id = message.photo[-1].file_id
        logging.info(f"[SCREENSHOT] Got photo file_id: {photo_file_id[:30]}...")
        
        # Create completion record with screenshot
        await task_repo.create_completion(
            user_id=user.id,
            task_id=task_id,
            screenshot_file_id=photo_file_id,
        )
        logging.info(f"[SCREENSHOT] Completion created for task {task_id}")
        
        if lang == "ru":
            text = (
                f"✅ Задание #{task_id} отправлено на проверку!\n\n"
                f"📸 Скриншот получен.\n"
                f"💰 Награда {task.reward:.4f} TON будет начислена\n"
                f"после подтверждения админом."
            )
        else:
            text = (
                f"✅ Task #{task_id} submitted for review!\n\n"
                f"📸 Screenshot received.\n"
                f"💰 Reward of {task.reward:.4f} TON will be credited\n"
                f"after admin confirmation."
            )
        
        from app.keyboards import get_back_keyboard
        await message.answer(text, reply_markup=get_back_keyboard("tasks", lang))
        logging.info("[SCREENSHOT] Done!")
        await state.clear()
        
    except Exception as e:
        logging.error(f"[SCREENSHOT] Error: {e}", exc_info=True)
        try:
            await message.answer(f"❌ Error: {str(e)[:100]}")
        except:
            pass
        await state.clear()


@router.callback_query(F.data.startswith("task_complete:"))
async def handle_task_complete(
    callback: types.CallbackQuery,
    session,
    user,
):
    lang = get_lang(user)
    task_id = int(callback.data.split(":")[1])

    task_repo = TaskRepository(session)
    task = await task_repo.get_by_id(task_id)

    if not task:
        await callback.answer("❌ Task not found", show_alert=True)
        return

    # Check if user already completed
    existing = await task_repo.get_user_task_completion(user.id, task_id)
    if existing:
        msg = "❌ Вы уже выполнили это задание." if lang == "ru" else "❌ You already completed this task."
        await callback.answer(msg, show_alert=True)
        return

    # Create completion record (pending admin review)
    await task_repo.create_completion(
        user_id=user.id,
        task_id=task_id,
    )

    if lang == "ru":
        text = (
            f"✅ Задание #{task_id} отправлено на проверку!\n\n"
            f"💰 Награда {task.reward:.4f} TON будет начислена\n"
            f"после подтверждения админом."
        )
    else:
        text = (
            f"✅ Task #{task_id} submitted for review!\n\n"
            f"💰 Reward of {task.reward:.4f} TON will be credited\n"
            f"after admin confirmation."
        )

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("tasks", lang),
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════
# ADMIN: Create tasks
# ══════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin_task_create")
async def admin_create_task_start(
    callback: types.CallbackQuery,
    state: FSMContext,
    session,
    user,
):
    import logging
    logging.info(f"[ADMIN] admin_create_task_start called: callback.data={callback.data}")
    
    if not user or user.telegram_id not in config.ADMIN_IDS:
        logging.warning(f"[ADMIN] Access denied: user={user}")
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    try:
        lang = get_lang(user)
        logging.info(f"[ADMIN] User lang: {lang}")

        builder = InlineKeyboardBuilder()
        builder.button(text="📢 Подписка" if lang == "ru" else "📢 Subscribe", callback_data="admin_cat_subscribe")
        builder.button(text="🤖 Боты" if lang == "ru" else "🤖 Bots", callback_data="admin_cat_bots")
        builder.button(text="👥 Группы" if lang == "ru" else "👥 Groups", callback_data="admin_cat_groups")
        builder.button(text="➕ Своё" if lang == "ru" else "➕ Custom", callback_data="admin_cat_custom")
        builder.button(text="🔙 Назад" if lang == "ru" else "🔙 Back", callback_data="admin_panel")
        builder.adjust(3, 1, 1)

        await callback.message.edit_text(
            "➕ Создать задание\n\nВыберите категорию:" if lang == "ru" else "➕ Create Task\n\nSelect category:",
            reply_markup=builder.as_markup(),
        )
        await callback.answer()
        logging.info("[ADMIN] admin_create_task_start completed")
    except Exception as e:
        logging.error(f"[ADMIN] Error in admin_create_task_start: {e}", exc_info=True)
        await callback.answer(f"⚠️ Error: {str(e)[:50]}", show_alert=True)


@router.callback_query(F.data.startswith("admin_cat_"))
async def admin_select_category(
    callback: types.CallbackQuery,
    state: FSMContext,
    session,
    user,
):
    import logging
    logging.info(f"[ADMIN] admin_select_category called: callback.data={callback.data}")
    
    if not user or user.telegram_id not in config.ADMIN_IDS:
        logging.warning(f"[ADMIN] Access denied in admin_select_category")
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    try:
        lang = get_lang(user)
        category = callback.data.replace("admin_cat_", "")
        logging.info(f"[ADMIN] Category: {category}")

        await state.update_data(admin_task_category=category)

        # Ask for check type (auto or manual)
        builder = InlineKeyboardBuilder()
        builder.button(
            text="🤖 Автоматическая" if lang == "ru" else "🤖 Auto",
            callback_data="check_type_auto"
        )
        builder.button(
            text="📸 Ручная" if lang == "ru" else "📸 Manual",
            callback_data="check_type_manual"
        )
        builder.button(
            text="🔙 Назад" if lang == "ru" else "🔙 Back",
            callback_data="admin_task_create"
        )
        builder.adjust(2, 1)

        check_type_text = (
            "➕ Создать задание\n\nВыберите тип проверки:\n\n"
            "🤖 Автоматическая — бот сам проверяет подписку\n"
            "📸 Ручная — админ проверяет скриншот"
        )
        check_type_text_en = (
            "➕ Create Task\n\nSelect check type:\n\n"
            "🤖 Auto — bot checks subscription automatically\n"
            "📸 Manual — admin checks screenshot"
        )

        await callback.message.edit_text(
            check_type_text if lang == "ru" else check_type_text_en,
            reply_markup=builder.as_markup(),
        )
        await callback.answer()
        logging.info("[ADMIN] admin_select_category completed")
    except Exception as e:
        logging.error(f"[ADMIN] Error in admin_select_category: {e}", exc_info=True)
        await callback.answer(f"⚠️ Error: {str(e)[:50]}", show_alert=True)

        await callback.answer()
        logging.info("[ADMIN] admin_select_category completed")
    except Exception as e:
        logging.error(f"[ADMIN] Error in admin_select_category: {e}", exc_info=True)
        await callback.answer(f"⚠️ Error: {str(e)[:50]}", show_alert=True)


@router.callback_query(F.data.in_(["check_type_auto", "check_type_manual"]))
async def admin_select_check_type(
    callback: types.CallbackQuery,
    state: FSMContext,
    user,
):
    if not user or user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    
    # Get check_type from callback data
    check_type = "manual" if callback.data == "check_type_manual" else "auto"
    await state.update_data(admin_check_type=check_type)

    data = await state.get_data()
    category = data.get("admin_task_category", "")

    if category == "custom":
        await callback.message.edit_text(
            "➕ Своё задание\n\nВведите описание:" if lang == "ru" else "➕ Custom Task\n\nEnter task description:",
            reply_markup=get_back_keyboard("admin_task_create", lang),
        )
        await state.set_state(AdminTaskStates.waiting_description)
    else:
        cat_label = {
            "subscribe": ("Канал", "Channel"),
            "bots": ("Бот", "Bot"),
            "groups": ("Группа", "Group"),
        }.get(category, ("", ""))
        label = cat_label[0] if lang == "ru" else cat_label[1]
        
        # Show actual check_type
        check_type_label = "📸 Ручная" if check_type == "manual" else "🤖 Авто"
        
        if lang == "ru":
            text = f"📝 Задание ({label})\n{check_type_label}\n\nОтправьте Telegram-ссылку\n(например https://t.me/...):"
        else:
            text = f"📝 {label} Task\n{check_type_label}\n\nSend the Telegram link (e.g. https://t.me/...):"
        await callback.message.edit_text(
            text,
            reply_markup=get_back_keyboard("admin_task_create", lang),
        )
        await state.set_state(AdminTaskStates.waiting_link)
        logging.info(f"[ADMIN] Set state to waiting_link")

    await callback.answer()


@router.message(AdminTaskStates.waiting_link)
async def admin_process_link(
    message: types.Message,
    state: FSMContext,
    session,
    user,
):
    logging.info(f">>> ADMIN_LINK handler CALLED for {message.from_user.id}, text={message.text[:30]}")
    logging.info(f">>> user={user}, session={session}")
    logging.info(f">>> current state: {await state.get_state()}")
    
    if not user or user.telegram_id not in config.ADMIN_IDS:
        logging.error(">> ACCESS DENIED")
        await message.answer("⛔️ Access denied.")
        return

    lang = get_lang(user)
    link = message.text.strip()
    logging.info(f">> Processing link: {link}")
    
    if not link.startswith("https://t.me/"):
        await message.answer(
            "❌ Неверная ссылка. Должна начинаться с https://t.me/" if lang == "ru"
            else "❌ Invalid link. Must start with https://t.me/"
        )
        return

    await state.update_data(admin_task_link=link)

    if lang == "ru":
        text = f"✅ Ссылка сохранена: {link}\n\nВведите сумму награды в TON (например 0.05):"
    else:
        text = f"✅ Link saved: {link}\n\nEnter reward amount in TON (e.g. 0.05):"

    await message.answer(
        text,
        reply_markup=get_back_keyboard("admin_task_create", lang),
    )
    await state.set_state(AdminTaskStates.waiting_reward)
    print(">> LINK HANDLER COMPLETE!")
    logging.info(f"[ADMIN_LINK] Done, now waiting for reward")


@router.message(AdminTaskStates.waiting_description)
async def admin_process_description(
    message: types.Message,
    state: FSMContext,
    session,
    user,
):
    if not user or user.telegram_id not in config.ADMIN_IDS:
        return

    lang = get_lang(user)
    description = message.text.strip()
    if len(description) < 3:
        await message.answer(
            "❌ Слишком короткое. Минимум 3 символа." if lang == "ru"
            else "❌ Too short. At least 3 characters."
        )
        return

    await state.update_data(admin_task_description=description)

    if lang == "ru":
        text = f"✅ Описание сохранено.\n\nВведите сумму награды в TON (например 0.1):"
    else:
        text = f"✅ Description saved.\n\nEnter reward amount in TON (e.g. 0.1):"

    await message.answer(
        text,
        reply_markup=get_back_keyboard("admin_task_create", lang),
    )
    await state.set_state(AdminTaskStates.waiting_reward)


@router.message(AdminTaskStates.waiting_reward)
async def admin_process_reward(
    message: types.Message,
    state: FSMContext,
    session,
    user,
):
    if not user or user.telegram_id not in config.ADMIN_IDS:
        return

    lang = get_lang(user)

    try:
        reward = float(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Введите число (например 0.05)" if lang == "ru"
            else "❌ Enter a number (e.g. 0.05)"
        )
        return

    if reward <= 0 or reward > 1000:
        await message.answer(
            "❌ Награда должна быть от 0.001 до 1000 TON." if lang == "ru"
            else "❌ Reward must be between 0.001 and 1000 TON."
        )
        return

    data = await state.get_data()
    category = data.get("admin_task_category", "custom")
    link = data.get("admin_task_link", "")
    description = data.get("admin_task_description", "")
    check_type = data.get("admin_check_type", "auto")
    
    chat_id = None
    bot_username = None
    
    if category in ("subscribe", "groups") and link:
        chat_id = link.replace("https://t.me/", "")
    elif category == "bots" and link:
        bot_username = link.replace("https://t.me/", "").replace("@", "")

    cat_labels = {
        "subscribe": "📢",
        "bots": "🤖",
        "groups": "👥",
        "custom": "➕",
    }
    prefix = cat_labels.get(category, "📋")

    if category == "custom":
        title = f"{prefix} {description[:50]}"
        desc = description
    else:
        name = link.replace("https://t.me/", "@")
        title = f"{prefix} {name}"
        desc = link

    task_repo = TaskRepository(session)
    task = await task_repo.create(
        user_id=user.id,
        title=title,
        description=desc,
        reward=reward,
        category=category,
        chat_id=chat_id,
        bot_username=bot_username,
        check_type=check_type,
    )

    await state.clear()

    from app.keyboards import get_admin_menu_keyboard

    check_type_label = "🤖 Авто" if check_type == "auto" else "📸 Ручная" if lang == "ru" else ("🤖 Auto" if check_type == "auto" else "📸 Manual")

    if lang == "ru":
        text = (
            f"✅ Задание создано!\n\n"
            f"📋 #{task.id} — {title}\n"
            f"💰 Награда: {reward:.4f} TON\n"
            f"📂 Категория: {category}\n"
            f"🔍 Проверка: {check_type_label}"
        )
    else:
        text = (
            f"✅ Task created!\n\n"
            f"📋 #{task.id} — {title}\n"
            f"💰 Reward: {reward:.4f} TON\n"
            f"📂 Category: {category}"
        )

    await message.answer(
        text,
        reply_markup=get_admin_menu_keyboard(get_lang(user)),
    )
