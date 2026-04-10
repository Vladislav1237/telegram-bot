"""
Admin panel handlers for task review and withdrawal management.
"""
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database.repositories import (
    TaskRepository, WithdrawalRepository, UserRepository,
    PromoCodeRepository, AdminLogRepository
)
from app.models import TaskStatus, WithdrawalStatus
from app.keyboards import (
    get_task_review_keyboard, get_withdrawal_action_keyboard,
    get_admin_menu_keyboard, get_back_keyboard, get_tasks_keyboard,
    get_task_category_keyboard, get_task_check_type_keyboard
)
from app.config import config

router = Router()


def get_lang(user) -> str:
    lang = getattr(user, "language_code", "en") or "en"
    return lang if lang in ("ru", "en") else "en"


class AdminStates(StatesGroup):
    waiting_for_promo_amount = State()
    waiting_for_promo_uses = State()
    waiting_for_reject_reason = State()
    waiting_for_reject_withdraw_reason = State()
    # States for creating tasks
    waiting_for_task_category = State()
    waiting_for_task_check_type = State()
    waiting_for_task_title = State()
    waiting_for_task_description = State()
    waiting_for_task_target = State()
    waiting_for_task_reward = State()
    waiting_for_task_screenshots_count = State()


# ── /admin command ───────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin(message: types.Message, session):
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(message.from_user.id)
    if not user or user.telegram_id not in config.ADMIN_IDS:
        await message.answer("⛔️ Access denied.")
        return
    lang = get_lang(user)
    title = "🛠️ Админ-панель\n\nВыберите:" if lang == "ru" else "🛠️ Admin Panel\n\nSelect:"
    await message.answer(title, reply_markup=get_admin_menu_keyboard(lang))


@router.callback_query(F.data == "admin_panel")
async def handle_admin_menu(callback: types.CallbackQuery, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return
    lang = get_lang(user)
    title = "🛠️ Админ-панель\n\nВыберите:" if lang == "ru" else "🛠️ Admin Panel\n\nSelect:"
    await callback.message.edit_text(title, reply_markup=get_admin_menu_keyboard(lang))
    await callback.answer()


# ── Task Review Queue ────────────────────────────────────────────
@router.callback_query(F.data == "admin_tasks_queue")
async def handle_admin_tasks_queue(callback: types.CallbackQuery, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    task_repo = TaskRepository(session)
    pending_tasks = await task_repo.get_pending_tasks()

    if not pending_tasks:
        empty_text = (
            "📋 Задания на проверку\n\n✅ Нет заданий!" if lang == "ru"
            else "📋 Pending Tasks\n\n✅ No pending tasks!"
        )
        await callback.message.edit_text(
            empty_text,
            reply_markup=get_admin_menu_keyboard(lang),
        )
        await callback.answer()
        return

    task = pending_tasks[0]
    lbl_review = f"📋 Задание #{task.id}" if lang == "ru" else f"📋 Task Review #{task.id}"
    lbl_user = "👤 Пользователь:" if lang == "ru" else "👤 User:"
    lbl_title = "📝 Название:" if lang == "ru" else "📝 Title:"
    lbl_desc = "📄 Описание:" if lang == "ru" else "📄 Description:"
    lbl_reward = "💰 Награда:" if lang == "ru" else "💰 Reward:"
    lbl_submitted = "⏳ Отправлено:" if lang == "ru" else "⏳ Submitted:"

    text = (
        f"{lbl_review}\n\n"
        f"{lbl_user} @{task.user.username or 'N/A'} ({task.user.telegram_id})\n"
        f"{lbl_title} {task.title}\n"
    )
    if task.description:
        text += f"{lbl_desc} {task.description}\n"
    text += f"{lbl_reward} {task.reward:.4f} TON\n"
    text += f"{lbl_submitted} {task.created_at.strftime('%Y-%m-%d %H:%M')}\n"
    
    # Show forwarded chat info if available
    if hasattr(task, 'forwarded_from_chat_id') and task.forwarded_from_chat_id:
        lbl_forwarded = "📬 Переслано из:" if lang == "ru" else "📬 Forwarded from:"
        text += f"{lbl_forwarded} {task.forwarded_from_chat_id}\n"

    await callback.message.edit_text(text, reply_markup=get_task_review_keyboard(task.id))

    if task.screenshot_file_id:
        screenshot_caption = (
            f"📸 Скриншот задания #{task.id}" if lang == "ru"
            else f"📸 Screenshot for task #{task.id}"
        )
        await callback.message.answer_photo(
            photo=task.screenshot_file_id,
            caption=screenshot_caption,
        )
    
    # Show info about forwarded message
    if hasattr(task, 'forwarded_from_chat_id') and task.forwarded_from_chat_id:
        forward_info = (
            f"📬 Сообщение переслано из чата ID: {task.forwarded_from_chat_id}" if lang == "ru"
            else f"📬 Message forwarded from chat ID: {task.forwarded_from_chat_id}"
        )
        await callback.message.answer(forward_info)
    
    await callback.answer()


@router.callback_query(F.data.startswith("task_approve:"))
async def handle_task_approve(callback: types.CallbackQuery, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    task_id = int(callback.data.split(":")[1])
    task_repo = TaskRepository(session)
    user_repo = UserRepository(session)
    admin_log_repo = AdminLogRepository(session)

    task = await task_repo.get_by_id(task_id)
    if not task:
        await callback.answer("❌ Task not found.", show_alert=True)
        return

    await task_repo.update_status(task_id=task_id, status=TaskStatus.APPROVED, reviewed_by=user.id)
    await user_repo.update_balance(task.user_id, task.reward, freeze=False)

    await admin_log_repo.create(
        admin_id=user.telegram_id, action="approve_task",
        target_type="task", target_id=task_id,
        details=f"Approved task #{task_id}, reward: {task.reward}",
    )

    approved_text = (
        "✅ Задание одобрено! Награда начислена." if lang == "ru"
        else "✅ Task approved! Reward credited."
    )
    await callback.answer(approved_text, show_alert=True)
    await handle_admin_tasks_queue(callback, session, user)


@router.callback_query(F.data.startswith("task_reject:"))
async def handle_task_reject(callback: types.CallbackQuery, state: FSMContext, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    task_id = int(callback.data.split(":")[1])
    await state.update_data(reject_task_id=task_id)

    reject_text = (
        "❌ Отклонить\n\nВведите причину\n(или /skip):" if lang == "ru"
        else "❌ Reject Task\n\nEnter rejection reason\n(or /skip):"
    )
    await callback.message.answer(
        reject_text,
        reply_markup=get_back_keyboard("admin_tasks_queue"),
    )
    await state.set_state(AdminStates.waiting_for_reject_reason)
    await callback.answer()


@router.message(AdminStates.waiting_for_reject_reason)
async def process_reject_reason(message: types.Message, state: FSMContext, session, user):
    data = await state.get_data()
    task_id = data.get("reject_task_id")
    if not task_id:
        await state.clear()
        return

    lang = get_lang(user)
    comment = message.text.strip()
    if comment == "/skip":
        comment = None

    task_repo = TaskRepository(session)
    admin_log_repo = AdminLogRepository(session)

    await task_repo.update_status(task_id=task_id, status=TaskStatus.REJECTED, admin_comment=comment, reviewed_by=user.id)
    await admin_log_repo.create(
        admin_id=user.telegram_id, action="reject_task",
        target_type="task", target_id=task_id,
        details=f"Rejected #{task_id}. Comment: {comment}",
    )
    await state.clear()
    rejected_text = (
        f"❌ Задание #{task_id} отклонено." if lang == "ru"
        else f"❌ Task #{task_id} rejected."
    )
    await message.answer(rejected_text, reply_markup=get_admin_menu_keyboard(lang))


# ── Withdrawal Review ────────────────────────────────────────────
@router.callback_query(F.data == "admin_withdrawals_queue")
async def handle_admin_withdrawals_queue(callback: types.CallbackQuery, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    withdraw_repo = WithdrawalRepository(session)
    pending = await withdraw_repo.get_pending_withdrawals()

    if not pending:
        empty_text = (
            "💸 Заявки на вывод\n\n✅ Нет заявок!" if lang == "ru"
            else "💸 Pending Withdrawals\n\n✅ None!"
        )
        await callback.message.edit_text(
            empty_text,
            reply_markup=get_admin_menu_keyboard(lang),
        )
        await callback.answer()
        return

    w = pending[0]
    lbl_withdrawal = f"💸 Вывод #{w.id}" if lang == "ru" else f"💸 Withdrawal #{w.id}"
    lbl_amount = "💰 Сумма:" if lang == "ru" else "💰 Amount:"
    lbl_wallet = "🏦 Кошелёк:" if lang == "ru" else "🏦 Wallet:"

    text = (
        f"{lbl_withdrawal}\n\n"
        f"👤 @{w.user.username or 'N/A'} ({w.user.telegram_id})\n"
        f"{lbl_amount} {w.amount:.4f} TON\n"
        f"{lbl_wallet} <code>{w.wallet_address}</code>\n"
        f"⏳ {w.created_at.strftime('%Y-%m-%d %H:%M')}"
    )

    await callback.message.edit_text(text, reply_markup=get_withdrawal_action_keyboard(w.id))
    await callback.answer()


@router.callback_query(F.data.startswith("withdraw_approve:"))
async def handle_withdraw_approve(callback: types.CallbackQuery, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    wid = int(callback.data.split(":")[1])
    withdraw_repo = WithdrawalRepository(session)
    admin_log_repo = AdminLogRepository(session)

    w = await withdraw_repo.get_by_id(wid)
    if not w:
        await callback.answer("❌ Not found.", show_alert=True)
        return

    import hashlib
    tx = hashlib.sha256(f"{wid}{user.telegram_id}".encode()).hexdigest()[:64]

    await withdraw_repo.update_status(wid, WithdrawalStatus.COMPLETED, processed_by=user.id, transaction_hash=tx)
    await admin_log_repo.create(
        admin_id=user.telegram_id, action="approve_withdrawal",
        target_type="withdrawal", target_id=wid,
        details=f"Approved #{wid} for {w.amount} TON",
    )

    approved_text = "✅ Одобрено!" if lang == "ru" else "✅ Approved!"
    await callback.answer(approved_text, show_alert=True)
    await handle_admin_withdrawals_queue(callback, session, user)


@router.callback_query(F.data.startswith("withdraw_reject:"))
async def handle_withdraw_reject(callback: types.CallbackQuery, state: FSMContext, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    wid = int(callback.data.split(":")[1])
    await state.update_data(reject_withdrawal_id=wid)

    reject_text = (
        "❌ Отклонить вывод\n\nВведите причину:" if lang == "ru"
        else "❌ Reject Withdrawal\n\nEnter reason:"
    )
    await callback.message.answer(
        reject_text,
        reply_markup=get_back_keyboard("admin_withdrawals_queue"),
    )
    await state.set_state(AdminStates.waiting_for_reject_withdraw_reason)
    await callback.answer()


@router.message(AdminStates.waiting_for_reject_withdraw_reason)
async def process_reject_withdraw_reason(message: types.Message, state: FSMContext, session, user):
    data = await state.get_data()
    wid = data.get("reject_withdrawal_id")
    if not wid:
        await state.clear()
        return

    lang = get_lang(user)
    comment = message.text.strip()
    withdraw_repo = WithdrawalRepository(session)
    user_repo = UserRepository(session)
    admin_log_repo = AdminLogRepository(session)

    w = await withdraw_repo.get_by_id(wid)
    if w:
        await user_repo.update_balance(w.user_id, w.amount, freeze=False)
        await withdraw_repo.update_status(wid, WithdrawalStatus.REJECTED, admin_comment=comment, processed_by=user.id)
        await admin_log_repo.create(
            admin_id=user.telegram_id, action="reject_withdrawal",
            target_type="withdrawal", target_id=wid,
            details=f"Rejected #{wid}. {comment}",
        )

    await state.clear()
    rejected_text = (
        f"❌ Вывод #{wid} отклонён. Средства возвращены." if lang == "ru"
        else f"❌ Withdrawal #{wid} rejected. Refunded."
    )
    await message.answer(rejected_text, reply_markup=get_admin_menu_keyboard(lang))


# ── Promo Code Creation ─────────────────────────────────────────
@router.callback_query(F.data == "admin_promo_create")
async def handle_admin_promo_create(callback: types.CallbackQuery, state: FSMContext, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    promo_text = (
        "🎁 Создать промокод\n\nВведите сумму награды (TON):" if lang == "ru"
        else "🎁 Create Promo Code\n\nEnter reward amount (TON):"
    )
    await callback.message.answer(
        promo_text,
        reply_markup=get_back_keyboard("admin_panel"),
    )
    await state.set_state(AdminStates.waiting_for_promo_amount)
    await callback.answer()


@router.message(AdminStates.waiting_for_promo_amount)
async def process_promo_amount(message: types.Message, state: FSMContext, user):
    lang = get_lang(user)
    try:
        amount = float(message.text.strip())
    except ValueError:
        err = "❌ Введите число." if lang == "ru" else "❌ Enter a number."
        await message.answer(err)
        return
    if amount <= 0:
        err = "❌ Должно быть > 0." if lang == "ru" else "❌ Must be > 0."
        await message.answer(err)
        return
    await state.update_data(promo_amount=amount)
    confirm_text = (
        f"✅ Награда: {amount:.4f} TON\n\nВведите макс. кол-во использований:" if lang == "ru"
        else f"✅ Reward: {amount:.4f} TON\n\nEnter max uses:"
    )
    await message.answer(confirm_text, reply_markup=get_back_keyboard("admin_panel"))
    await state.set_state(AdminStates.waiting_for_promo_uses)


@router.message(AdminStates.waiting_for_promo_uses)
async def process_promo_uses(message: types.Message, state: FSMContext, session, user):
    lang = get_lang(user)
    try:
        uses = int(message.text.strip())
    except ValueError:
        err = "❌ Введите число." if lang == "ru" else "❌ Enter a number."
        await message.answer(err)
        return
    if uses <= 0:
        err = "❌ Должно быть > 0." if lang == "ru" else "❌ Must be > 0."
        await message.answer(err)
        return

    data = await state.get_data()
    amount = data.get("promo_amount", 0)

    from app.utils import generate_promo_code
    code = generate_promo_code()

    promo_repo = PromoCodeRepository(session)
    await promo_repo.create(code=code, reward_amount=amount, max_uses=uses)

    await state.clear()

    lbl_code = "🏷️ Код:" if lang == "ru" else "🏷️ Code:"
    lbl_reward = "💰 Награда:" if lang == "ru" else "💰 Reward:"
    lbl_max = "📊 Макс. использований:" if lang == "ru" else "📊 Max uses:"
    created_title = "✅ Промокод создан!" if lang == "ru" else "✅ Promo code created!"

    await message.answer(
        f"{created_title}\n\n"
        f"{lbl_code} <code>{code}</code>\n"
        f"{lbl_reward} {amount:.4f} TON\n"
        f"{lbl_max} {uses}",
        reply_markup=get_admin_menu_keyboard(lang),
    )


# ── Promo Code List & Delete ─────────────────────────────────────
@router.callback_query(F.data == "admin_promo_list")
async def handle_admin_promo_list(callback: types.CallbackQuery, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    promo_repo = PromoCodeRepository(session)
    promos = await promo_repo.get_all()

    if not promos:
        text = "🏷️ Промокоды\n\nНет промокодов." if lang == "ru" else "🏷️ Promo Codes\n\nNo promo codes."
        await callback.message.edit_text(text, reply_markup=get_admin_menu_keyboard(lang))
        await callback.answer()
        return

    text = "🏷️ Промокоды\n\n" if lang == "ru" else "🏷️ Promo Codes\n\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    for p in promos[:15]:
        remaining = p.max_uses - p.current_uses
        status = "✅" if p.is_active and remaining > 0 else "❌"
        text += (
            f"{status} <code>{p.code}</code>\n"
            f"   💰 {p.reward_amount:.4f} TON | "
        )
        if lang == "ru":
            text += f"Осталось: {remaining}/{p.max_uses}\n\n"
        else:
            text += f"Left: {remaining}/{p.max_uses}\n\n"

        btn_label = f"🗑 {p.code}" 
        builder.button(text=btn_label, callback_data=f"admin_promo_del:{p.id}")

    builder.button(
        text="🔙 Назад" if lang == "ru" else "🔙 Back",
        callback_data="admin_panel",
    )
    builder.adjust(2, 2, 2, 2, 2, 2, 2, 1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_promo_del:"))
async def handle_admin_promo_delete(callback: types.CallbackQuery, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    promo_id = int(callback.data.split(":")[1])
    promo_repo = PromoCodeRepository(session)

    promo = await promo_repo.get_by_id(promo_id)
    if not promo:
        await callback.answer("❌", show_alert=True)
        return

    code = promo.code
    await promo_repo.delete(promo_id)

    msg = f"🗑 Промокод <code>{code}</code> удалён." if lang == "ru" else f"🗑 Promo <code>{code}</code> deleted."
    await callback.answer(msg.replace("<code>", "").replace("</code>", ""), show_alert=True)

    # Refresh list
    await handle_admin_promo_list(callback, session, user)


# ── Admin Users ──────────────────────────────────────────────────
@router.callback_query(F.data == "admin_users")
async def handle_admin_users(callback: types.CallbackQuery, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    user_repo = UserRepository(session)
    users = await user_repo.get_all_users()

    header = (
        f"👥 Все пользователи ({len(users)})\n\n" if lang == "ru"
        else f"👥 All Users ({len(users)})\n\n"
    )
    text = header
    for u in users[:20]:
        text += f"• @{u.username or 'N/A'} — {u.balance:.4f} TON\n"

    if len(users) > 20:
        more = (
            f"\n... и ещё {len(users) - 20}" if lang == "ru"
            else f"\n... and {len(users) - 20} more"
        )
        text += more

    await callback.message.edit_text(text, reply_markup=get_back_keyboard("admin_panel"))


# ── Admin All Tasks ─────────────────────────────────────────────────
@router.callback_query(F.data == "admin_all_tasks")
async def handle_admin_all_tasks(callback: types.CallbackQuery, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    task_repo = TaskRepository(session)
    tasks = await task_repo.get_all_tasks()

    if not tasks:
        empty_text = "📝 Все задания\n\n✅ Нет заданий!" if lang == "ru" else "📝 All Tasks\n\n✅ No tasks!"
        await callback.message.edit_text(empty_text, reply_markup=get_admin_menu_keyboard(lang))
        await callback.answer()
        return

    # Simple text list with stats
    text = f"📝 Все задания ({len(tasks)})\n\n"
    
    for task in tasks[:10]:
        completions = await task_repo.get_completion_count(task.id)
        status = "✅" if task.is_active else "⛔️"
        check = "🤖" if task.check_type == "auto" else "📸"
        text += f"{status} #{task.id} {task.title[:20]} | {task.reward:.1f} | ✅{completions} | {check}\n"
    
    if len(tasks) > 10:
        text += f"\n... и ещё {len(tasks) - 10} заданий"
    
    text += "\n\nНажмите на задание для управления:" if lang == "ru" else "\nClick on a task to manage:"
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    for task in tasks[:10]:
        completions = await task_repo.get_completion_count(task.id)
        status = "✅" if task.is_active else "⛔️"
        label = f"{status} #{task.id} {task.title[:15]}... ({completions}✅)"
        builder.button(text=label, callback_data=f"task_edit:{task.id}")
    
    if lang == "ru":
        builder.button(text="🔙 Назад", callback_data="admin_panel")
    else:
        builder.button(text="🔙 Back", callback_data="admin_panel")
    
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("task_edit:"))
async def handle_task_edit(callback: types.CallbackQuery, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    task_id = int(callback.data.split(":")[1])
    task_repo = TaskRepository(session)
    
    task = await task_repo.get_by_id(task_id)
    if not task:
        await callback.answer("Task not found!", show_alert=True)
        return
    
    completions = await task_repo.get_completion_count(task.id)
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    # Always show both buttons
    builder.button(text="✅ Активировать" if lang == "ru" else "✅ Activate", callback_data=f"task_act:{task.id}")
    builder.button(text="⛔️ Деактивировать" if lang == "ru" else "⛔️ Deactivate", callback_data=f"task_deact:{task.id}")
    builder.button(text="🗑️ Удалить" if lang == "ru" else "🗑️ Delete", callback_data=f"task_del:{task.id}")
    builder.button(text="↩️ Назад" if lang == "ru" else "↩️ Back", callback_data="admin_all_tasks")
    
    builder.adjust(2, 1, 1)
    
    is_active = "АКТИВНО" if task.is_active else "НЕАКТИВНО"
    check_text = "🤖 Авто" if task.check_type == "auto" else "📸 Ручная"
    
    text = (
        f"📝 Задание #{task.id}\n\n"
        f"📌 Название: {task.title}\n"
        f"💰 Награда: {task.reward:.4f} TON\n"
        f"📂 Категория: {task.category}\n"
        f"🔍 Проверка: {check_text}\n"
        f"📊 Статус: {is_active}\n\n"
        f"✅ Выполнений: {completions}\n\n"
        f"🔗 Ссылка: {task.description or 'N/A'}"
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# Task action handlers
@router.callback_query(F.data.startswith("task_act:"))
async def handle_task_activate(callback: types.CallbackQuery, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return
    
    task_id = int(callback.data.split(":")[1])
    task_repo = TaskRepository(session)
    task = await task_repo.get_by_id(task_id)
    if task:
        task.is_active = True
        await session.commit()
    
    await callback.answer("✅ Активировано!")
    await handle_task_edit(callback, session, user)


@router.callback_query(F.data.startswith("task_deact:"))
async def handle_task_deactivate(callback: types.CallbackQuery, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return
    
    task_id = int(callback.data.split(":")[1])
    task_repo = TaskRepository(session)
    task = await task_repo.get_by_id(task_id)
    if task:
        task.is_active = False
        await session.commit()
    
    await callback.answer("⛔️ Деактивировано!")
    await handle_task_edit(callback, session, user)


@router.callback_query(F.data.startswith("task_del:"))
async def handle_task_delete(callback: types.CallbackQuery, session, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return
    
    task_id = int(callback.data.split(":")[1])
    task_repo = TaskRepository(session)
    await task_repo.delete(task_id)
    
    await callback.answer("✅ Удалено!", show_alert=True)
    await handle_admin_all_tasks(callback, session, user)


# ── Create Task (Admin) ────────────────────────────────────────────
@router.callback_query(F.data == "admin_task_create")
async def handle_admin_task_create(callback: types.CallbackQuery, state: FSMContext, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    title = (
        "➕ Создать задание\n\nВыберите категорию:" if lang == "ru"
        else "➕ Create Task\n\nSelect category:"
    )
    await callback.message.answer(
        title,
        reply_markup=get_task_category_keyboard(lang),
    )
    await state.set_state(AdminStates.waiting_for_task_category)
    await callback.answer()


@router.callback_query(F.data.startswith("task_cat_"))
async def handle_task_category_select(callback: types.CallbackQuery, state: FSMContext, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    category = callback.data.replace("task_cat_", "")
    await state.update_data(task_category=category)

    # Now ask for check type
    check_title = (
        "🔍 Выберите тип проверки:" if lang == "ru"
        else "🔍 Select check type:"
    )
    await callback.message.answer(
        check_title,
        reply_markup=get_task_check_type_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("task_check_"))
async def handle_task_check_type_select(callback: types.CallbackQuery, state: FSMContext, user):
    if user.telegram_id not in config.ADMIN_IDS:
        await callback.answer("⛔️ Access denied.", show_alert=True)
        return

    lang = get_lang(user)
    check_type = callback.data.replace("task_check_", "")
    await state.update_data(task_check_type=check_type)

    # Now ask for task title
    title_prompt = (
        "📝 Введите название задания:" if lang == "ru"
        else "📝 Enter task title:"
    )
    await callback.message.answer(
        title_prompt,
        reply_markup=get_back_keyboard("admin_panel"),
    )
    await state.set_state(AdminStates.waiting_for_task_title)
    await callback.answer()


@router.message(AdminStates.waiting_for_task_title)
async def process_task_title(message: types.Message, state: FSMContext, user):
    lang = get_lang(user)
    title = message.text.strip()
    if not title:
        err = "❌ Название не может быть пустым." if lang == "ru" else "❌ Title cannot be empty."
        await message.answer(err)
        return
    
    await state.update_data(task_title=title)
    
    desc_prompt = (
        "📄 Введите описание задания (или ссылку):" if lang == "ru"
        else "📄 Enter task description (or link):"
    )
    await message.answer(
        desc_prompt,
        reply_markup=get_back_keyboard("admin_panel"),
    )
    await state.set_state(AdminStates.waiting_for_task_description)


@router.message(AdminStates.waiting_for_task_description)
async def process_task_description(message: types.Message, state: FSMContext, user):
    lang = get_lang(user)
    description = message.text.strip()
    if not description:
        err = "❌ Описание не может быть пустым." if lang == "ru" else "❌ Description cannot be empty."
        await message.answer(err)
        return
    
    await state.update_data(task_description=description)
    
    # For auto check with subscribe/bots/groups categories, ask for target username
    data = await state.get_data()
    check_type = data.get("task_check_type", "manual")
    category = data.get("task_category", "custom")
    
    if check_type == "auto" and category in ["subscribe", "bots", "groups"]:
        username_prompt = (
            "📢 Введите юзернейм канала/бота/группы (без @):" if lang == "ru"
            else "📢 Enter channel/bot/group username (without @):"
        )
        await message.answer(
            username_prompt,
            reply_markup=get_back_keyboard("admin_panel"),
        )
        await state.set_state(AdminStates.waiting_for_task_target)
        return
    
    # For manual tasks, ask for required screenshots count
    if check_type == "manual":
        screenshots_prompt = (
            "📸 Сколько скриншотов нужно отправить? (1-5):" if lang == "ru"
            else "📸 How many screenshots required? (1-5):"
        )
        await message.answer(
            screenshots_prompt,
            reply_markup=get_back_keyboard("admin_panel"),
        )
        await state.set_state(AdminStates.waiting_for_task_screenshots_count)
        return
    
    reward_prompt = (
        "💰 Введите награду в TON:" if lang == "ru"
        else "💰 Enter reward amount in TON:"
    )
    await message.answer(
        reward_prompt,
        reply_markup=get_back_keyboard("admin_panel"),
    )
    await state.set_state(AdminStates.waiting_for_task_reward)


@router.message(AdminStates.waiting_for_task_target)
async def process_task_target(message: types.Message, state: FSMContext, user):
    lang = get_lang(user)
    target_username = message.text.strip()
    if not target_username:
        err = "❌ Юзернейм не может быть пустым." if lang == "ru" else "❌ Username cannot be empty."
        await message.answer(err)
        return
    
    # Remove @ if present
    target_username = target_username.replace("@", "")
    await state.update_data(task_target_username=target_username)
    
    # For manual tasks with target, still need screenshots count
    data = await state.get_data()
    check_type = data.get("task_check_type", "manual")
    
    if check_type == "manual":
        screenshots_prompt = (
            "📸 Сколько скриншотов нужно отправить? (1-5):" if lang == "ru"
            else "📸 How many screenshots required? (1-5):"
        )
        await message.answer(
            screenshots_prompt,
            reply_markup=get_back_keyboard("admin_panel"),
        )
        await state.set_state(AdminStates.waiting_for_task_screenshots_count)
        return
    
    reward_prompt = (
        "💰 Введите награду в TON:" if lang == "ru"
        else "💰 Enter reward amount in TON:"
    )
    await message.answer(
        reward_prompt,
        reply_markup=get_back_keyboard("admin_panel"),
    )
    await state.set_state(AdminStates.waiting_for_task_reward)


@router.message(AdminStates.waiting_for_task_screenshots_count)
async def process_task_screenshots_count(message: types.Message, state: FSMContext, user):
    lang = get_lang(user)
    try:
        count = int(message.text.strip())
    except ValueError:
        err = "❌ Введите число." if lang == "ru" else "❌ Enter a number."
        await message.answer(err)
        return
    
    if count < 1 or count > 5:
        err = "❌ Должно быть от 1 до 5." if lang == "ru" else "❌ Must be between 1 and 5."
        await message.answer(err)
        return
    
    await state.update_data(task_screenshots_count=count)
    
    reward_prompt = (
        "💰 Введите награду в TON:" if lang == "ru"
        else "💰 Enter reward amount in TON:"
    )
    await message.answer(
        reward_prompt,
        reply_markup=get_back_keyboard("admin_panel"),
    )
    await state.set_state(AdminStates.waiting_for_task_reward)


@router.message(AdminStates.waiting_for_task_reward)
async def process_task_reward(message: types.Message, state: FSMContext, session, user):
    lang = get_lang(user)
    try:
        reward = float(message.text.strip())
    except ValueError:
        err = "❌ Введите число." if lang == "ru" else "❌ Enter a number."
        await message.answer(err)
        return
    
    if reward <= 0:
        err = "❌ Награда должна быть больше 0." if lang == "ru" else "❌ Reward must be > 0."
        await message.answer(err)
        return

    data = await state.get_data()
    category = data.get("task_category", "custom")
    check_type = data.get("task_check_type", "manual")
    title = data.get("task_title", "")
    description = data.get("task_description", "")
    target_username = data.get("task_target_username")
    screenshots_count = data.get("task_screenshots_count", 1)

    task_repo = TaskRepository(session)
    admin_log_repo = AdminLogRepository(session)

    # Create the task
    new_task = await task_repo.create(
        title=title,
        description=description,
        reward=reward,
        category=category,
        check_type=check_type,
        target_username=target_username,
        required_screenshots_count=screenshots_count,
        is_active=True,
        created_by=user.id,
    )

    await admin_log_repo.create(
        admin_id=user.telegram_id,
        action="create_task",
        target_type="task",
        target_id=new_task.id,
        details=f"Created task #{new_task.id}: {title}",
    )

    await state.clear()

    lbl_title = "📝 Название:" if lang == "ru" else "📝 Title:"
    lbl_desc = "📄 Описание:" if lang == "ru" else "📄 Description:"
    lbl_reward = "💰 Награда:" if lang == "ru" else "💰 Reward:"
    lbl_cat = "📂 Категория:" if lang == "ru" else "📂 Category:"
    lbl_check = "🔍 Проверка:" if lang == "ru" else "🔍 Check type:"
    created_title = "✅ Задание создано!" if lang == "ru" else "✅ Task created!"

    check_text = "🤖 Авто" if check_type == "auto" else "📸 Ручная"
    cat_text = {
        "subscribe": "📢 Подписка" if lang == "ru" else "📢 Subscribe",
        "bots": "🤖 Боты" if lang == "ru" else "🤖 Bots",
        "groups": "👥 Группы" if lang == "ru" else "👥 Groups",
        "custom": "✍️ Свое" if lang == "ru" else "✍️ Custom",
    }.get(category, category)

    await message.answer(
        f"{created_title}\n\n"
        f"{lbl_title} {title}\n"
        f"{lbl_desc} {description}\n"
        f"{lbl_reward} {reward:.4f} TON\n"
        f"{lbl_cat} {cat_text}\n"
        f"{lbl_check} {check_text}\n"
        f"ID: #{new_task.id}",
        reply_markup=get_admin_menu_keyboard(lang),
    )
