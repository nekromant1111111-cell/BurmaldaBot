"""Хендлеры для /start и /help."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.ai_service import clear_history

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Приветствие."""
    await message.answer(
        "👋 Привет! Я AI-бот.\n\n"
        "Что я умею:\n"
        "• Отвечать на любые вопросы\n"
        "• Искать в интернете: /поиск запрос\n"
        "• Код и команды — в красивых блоках\n\n"
        "Команды:\n"
        "/help — подробная справка\n"
        "/clear — очистить историю диалога\n\n"
        "Просто напиши мне что-нибудь!",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Справка."""
    await message.answer(
        "📖 <b>Справка по боту</b>\n\n"
        "💡 <b>Команды:</b>\n"
        "• /поиск запрос — найти в интернете (например: /поиск курс биткоина)\n"
        "• /clear — начать диалог заново\n"
        "• /help — эта справка\n\n"
        "💬 <b>Как пользоваться:</b>\n"
        "• Задавай вопросы как в обычном диалоге\n"
        "• Код и команды бот показывает в блоках — легко копировать\n"
        "• Длинные ответы разбиваются на несколько сообщений\n\n"
        "⚠️ <b>Ограничения:</b>\n"
        "• Поиск: до 3 запросов в минуту, чтобы не перегрузить сервер\n"
        "• История диалога хранится ~{max_history} сообщений",
        parse_mode="HTML",
    )


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    """Очистка истории диалога."""
    clear_history(message.from_user.id)
    await message.answer("🧹 История диалога очищена! Начинаем с чистого листа.")
