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
        "👋 Привет! Я AI-бот на базе <b>Google Gemini</b> (бесплатно).\n\n"
        "Что я умею:\n"
        "• Отвечать на любые вопросы\n"
        "• Искать информацию в интернете (просто попроси)\n"
        "• Читать веб-страницы по ссылкам\n\n"
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
        "Этот бот использует <b>Google Gemini API</b> (бесплатно).\n\n"
        "💡 <b>Советы:</b>\n"
        "• Задавай вопросы как в обычном диалоге\n"
        "• Если нужно что-то актуальное — попроси поискать в интернете\n"
        "• Присылай ссылки — я прочитаю содержимое\n"
        "• Используй /clear чтобы начать диалог заново\n\n"
        "⚠️ <b>Ограничения:</b>\n"
        "• История диалога хранится ~{max_history} сообщений\n"
        "• Если нужна новая тема — лучше очистить историю\n\n"
        "Создан с ❤️ на aiogram 3 + Gemini API",
        parse_mode="HTML",
    )


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    """Очистка истории диалога."""
    clear_history(message.from_user.id)
    await message.answer("🧹 История диалога очищена! Начинаем с чистого листа.")
