"""Хендлеры для /start, /help, /clear и автодетекта просьбы о помощи."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.ai_service import clear_history
from config import Config

logger = logging.getLogger(__name__)

router = Router()


def help_text() -> str:
    """Текст справки со всеми командами."""
    return (
        "📖 <b>Справка по боту</b>\n\n"
        "💡 <b>Команды:</b>\n"
        "• /поиск запрос — найти в интернете (например: /поиск курс биткоина)\n"
        "• /погода город — погода сейчас (например: /погода Сочи)\n"
        "• /мем — случайный мем из моей коллекции\n"
        "• /clear — начать диалог заново\n"
        "• /help — эта справка\n\n"
        "💬 <b>Как пользоваться:</b>\n"
        "• Просто задавай вопросы — если нужны свежие данные, "
        "бот сам найдёт их в интернете\n"
        "• Код и команды бот показывает в блоках — легко копировать\n"
        "• Длинные ответы разбиваются на несколько сообщений\n\n"
        "⚠️ <b>Ограничения:</b>\n"
        "• Поиск: до 3 запросов в минуту, чтобы не перегрузить сервер\n"
        f"• История диалога хранится ~{Config.MAX_HISTORY} сообщений\n"
    )


def is_help_request(message: Message) -> bool:
    """Фильтр: обычное сообщение (не команда), похожее на просьбу о помощи."""
    text = message.text or ""
    if not text or text.startswith("/"):
        return False

    t = text.lower().strip()
    if t in ("help", "хелп", "справка", "помощь", "помоги", "команды", "хочу знать команды"):
        return True

    return any(
        p in t
        for p in (
            "что ты умеешь", "что умеешь", "какие команды", "какие функции",
            "как пользоваться", "как тобой пользоваться", "как работает бот",
            "помощь по командам", "какие возможности", "список команд",
            "все команды", "как пользоваться ботом",
        )
    )


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Приветствие."""
    await message.answer(
        "👋 Привет! Я AI-бот.\n\n"
        "Что я умею:\n"
        "• Отвечать на любые вопросы\n"
        "• Сам искать свежие данные в интернете\n"
        "• Показывать погоду и курс валют\n"
        "• Код и команды — в красивых блоках\n\n"
        "Команды:\n"
        "/help — подробная справка\n"
        "/clear — очистить историю диалога\n\n"
        "Просто напиши мне что-нибудь!",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Справка со всеми командами."""
    await message.answer(help_text(), parse_mode="HTML")


@router.message(is_help_request)
async def auto_help(message: Message) -> None:
    """Если пользователь просит помощи — показываем справку вместо ответа AI."""
    logger.info(f"Авто-справка для {message.from_user.id}")
    await message.answer(help_text(), parse_mode="HTML")


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    """Очистка истории диалога."""
    clear_history(message.from_user.id)
    await message.answer("🧹 История диалога очищена! Начинаем с чистого листа.")
