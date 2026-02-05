from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from config import TELEGRAM_ADMIN_ID
from modules.database import db
from modules.logger import logger

admin_router = Router()

# Коллбэки
STATS_PERIOD_ALL = "stats_all"
STATS_PERIOD_MONTH = "stats_month"
STATS_PERIOD_WEEK = "stats_week"
STATS_PERIOD_TODAY = "stats_today"


@admin_router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Показывает кнопки выбора периода статистики"""

    if message.from_user.id != TELEGRAM_ADMIN_ID:
        await message.answer("❌ Доступ запрещён")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 За всё время", callback_data=STATS_PERIOD_ALL)],
        [InlineKeyboardButton(text="📈 За месяц", callback_data=STATS_PERIOD_MONTH)],
        [InlineKeyboardButton(text="📉 За неделю", callback_data=STATS_PERIOD_WEEK)],
        [InlineKeyboardButton(text="📅 За сегодня", callback_data=STATS_PERIOD_TODAY)],
    ])

    await message.answer("📊 Выберите период для статистики:", reply_markup=keyboard)


@admin_router.callback_query(F.data.in_([
    STATS_PERIOD_ALL, STATS_PERIOD_MONTH, STATS_PERIOD_WEEK, STATS_PERIOD_TODAY
]))
async def callback_stats(query: CallbackQuery):
    """Обрабатывает выбор периода и показывает статистику"""

    period_map = {
        STATS_PERIOD_ALL: None,
        STATS_PERIOD_MONTH: "month",
        STATS_PERIOD_WEEK: "week",
        STATS_PERIOD_TODAY: "today",
    }

    period = period_map[query.data]

    try:
        stats = await db.get_stats(period)
        text = _format_stats(stats, period)

        await query.message.edit_text(text, parse_mode="HTML")
        await query.answer()

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await query.message.edit_text(f"❌ Ошибка получения статистики: {e}")
        await query.answer()


@admin_router.message(Command("start"))
async def cmd_start(message: Message):
    """Команда /start"""

    if message.from_user.id != TELEGRAM_ADMIN_ID:
        await message.answer("❌ Доступ запрещён")
        return

    text = """
👋 Бот архивирования Реддита запущен

Доступные команды:
/stats - Просмотр статистики
/status - Статус работы
    """
    await message.answer(text)


@admin_router.message(Command("status"))
async def cmd_status(message: Message):
    """Статус работы бота"""

    if message.from_user.id != TELEGRAM_ADMIN_ID:
        await message.answer("❌ Доступ запрещён")
        return

    try:
        disk_usage = await db.get_disk_usage()
        disk_usage_gb = disk_usage / (1024 ** 3)

        text = f"""
✅ Бот работает

📊 Статус:
• Использование диска: {disk_usage_gb:.2f} GB / 3 GB
    """
        await message.answer(text)

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


def _format_stats(stats: dict, period: str = None) -> str:
    """Форматирует вывод статистики"""

    period_name = {
        None: "📊 За всё время",
        "month": "📈 За месяц",
        "week": "📉 За неделю",
        "today": "📅 За сегодня"
    }[period]

    bytes_gb = stats['bytes_uploaded'] / (1024 ** 3)

    return f"""
<b>{period_name}</b>

📤 Постов загружено: <code>{stats['posts_uploaded']}</code>
🎬 Файлов загружено: <code>{stats['files_uploaded']}</code>
💾 Размер данных: <code>{bytes_gb:.2f} GB</code>

❌ Постов с ошибками: <code>{stats['posts_failed']}</code>
⏭️  Пропущено постов: <code>{stats['posts_skipped']}</code>
    """
