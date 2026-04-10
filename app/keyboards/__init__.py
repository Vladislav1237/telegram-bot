"""
Inline keyboards for the Telegram bot.
"""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard(lang: str = "en", is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="💰 Баланс", callback_data="balance")
        builder.button(text="👥 Рефералы", callback_data="referrals")
        builder.button(text="📋 Задания", callback_data="tasks")
        builder.button(text="💸 Вывести", callback_data="withdraw")
        builder.button(text="🎁 Промокод", callback_data="promo")
        builder.button(text="⚙️ Настройки", callback_data="settings")
    else:
        builder.button(text="💰 Balance", callback_data="balance")
        builder.button(text="👥 Referrals", callback_data="referrals")
        builder.button(text="📋 Tasks", callback_data="tasks")
        builder.button(text="💸 Withdraw", callback_data="withdraw")
        builder.button(text="🎁 Promo Code", callback_data="promo")
        builder.button(text="⚙️ Settings", callback_data="settings")
    if is_admin:
        builder.button(text="🛠️ Админ-панель", callback_data="admin_panel")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def get_language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇬🇧 English", callback_data="lang_en")
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.adjust(2)
    return builder.as_markup()


def get_back_keyboard(callback: str = "main_menu", lang: str = "en") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔙 Назад" if lang == "ru" else "🔙 Back",
        callback_data=callback,
    )
    return builder.as_markup()


def get_tasks_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="📢 Подписка", callback_data="tasks_cat_subscribe")
        builder.button(text="🤖 Боты", callback_data="tasks_cat_bots")
        builder.button(text="👥 Группы", callback_data="tasks_cat_groups")
        builder.button(text="🔙 Назад", callback_data="main_menu")
    else:
        builder.button(text="📢 Subscribe", callback_data="tasks_cat_subscribe")
        builder.button(text="🤖 Bots", callback_data="tasks_cat_bots")
        builder.button(text="👥 Groups", callback_data="tasks_cat_groups")
        builder.button(text="🔙 Back", callback_data="main_menu")
    builder.adjust(3, 1)
    return builder.as_markup()


def get_confirm_keyboard(
    confirm_callback: str,
    cancel_callback: str,
    lang: str = "en",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Подтвердить" if lang == "ru" else "✅ Confirm",
        callback_data=confirm_callback,
    )
    builder.button(
        text="❌ Отмена" if lang == "ru" else "❌ Cancel",
        callback_data=cancel_callback,
    )
    builder.adjust(2)
    return builder.as_markup()


def get_task_review_keyboard(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve", callback_data=f"task_approve:{task_id}")
    builder.button(text="❌ Reject", callback_data=f"task_reject:{task_id}")
    builder.button(text="🔙 Back to Queue", callback_data="admin_tasks_queue")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_withdrawal_action_keyboard(withdrawal_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve & Pay", callback_data=f"withdraw_approve:{withdrawal_id}")
    builder.button(text="❌ Reject", callback_data=f"withdraw_reject:{withdrawal_id}")
    builder.button(text="🔙 Back to Queue", callback_data="admin_withdrawals_queue")
    builder.adjust(1, 1, 1)
    return builder.as_markup()


def get_admin_menu_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="📋 Задания на проверку", callback_data="admin_tasks_queue")
        builder.button(text="📝 Все задания", callback_data="admin_all_tasks")
        builder.button(text="➕ Создать задание", callback_data="admin_task_create")
        builder.button(text="💸 Заявки на вывод", callback_data="admin_withdrawals_queue")
        builder.button(text="🎁 Создать промокод", callback_data="admin_promo_create")
        builder.button(text="🏷️ Промокоды", callback_data="admin_promo_list")
        builder.button(text="👥 Пользователи", callback_data="admin_users")
        builder.button(text="🔙 Выйти", callback_data="main_menu")
    else:
        builder.button(text="📋 Pending Tasks", callback_data="admin_tasks_queue")
        builder.button(text="📝 All Tasks", callback_data="admin_all_tasks")
        builder.button(text="➕ Create Task", callback_data="admin_task_create")
        builder.button(text="💸 Pending Withdrawals", callback_data="admin_withdrawals_queue")
        builder.button(text="🎁 Create Promo Code", callback_data="admin_promo_create")
        builder.button(text="🏷️ Promo Codes", callback_data="admin_promo_list")
        builder.button(text="👥 All Users", callback_data="admin_users")
        builder.button(text="🔙 Exit Admin", callback_data="main_menu")
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()


def get_withdraw_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="💳 Создать заявку", callback_data="withdraw_create")
        builder.button(text="📜 История", callback_data="withdraw_history")
        builder.button(text="🔙 Назад", callback_data="main_menu")
    else:
        builder.button(text="💳 Create Withdrawal", callback_data="withdraw_create")
        builder.button(text="📜 History", callback_data="withdraw_history")
        builder.button(text="🔙 Back", callback_data="main_menu")
    builder.adjust(1, 1, 1)
    return builder.as_markup()
