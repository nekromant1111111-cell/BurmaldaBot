"""Команда /погода — погода в городе (бесплатный open-meteo API)."""

import logging

from aiogram import Router
from aiogram.types import Message

from app.services import weather_service

logger = logging.getLogger(__name__)

router = Router()


def is_weather_cmd(message: Message) -> bool:
    """Фильтр: сообщение начинается с /погода (с или без @имябота)."""
    text = message.text or ""
    if not text:
        return False
    first = text.split(maxsplit=1)[0]
    cmd = first.split("@")[0].lower()
    return cmd == "/погода"


@router.message(is_weather_cmd)
async def weather_handler(message: Message) -> None:
    """Обработчик /погода город"""
    parts = message.text.split(maxsplit=1)
    query = parts[1].strip() if len(parts) > 1 else "Москва"

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    result = await weather_service.get_weather_text(query)

    if result:
        await message.answer(result, parse_mode=None)
    else:
        await message.answer(
            "😔 Не удалось получить погоду. Проверь название города, "
            "например: /погода Сочи",
            parse_mode=None,
        )
