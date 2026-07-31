"""Основной хендлер: AI-чат.

Правила:
- В личном чате — отвечает на всё
- В группе — только если в сообщении есть слово "бурмалда"
"""

import logging

from aiogram import Router
from aiogram.types import Message

from app.services.ai_service import add_message, ask_llm, get_history

logger = logging.getLogger(__name__)

router = Router()

# Ключевое слово для активации в группах
TRIGGER_WORD = "бурмалда"


def _should_respond(message: Message) -> bool:
    """Проверяет, должен ли бот ответить на это сообщение."""
    # В личном чате — отвечаем на всё
    if message.chat.type == "private":
        return True

    # В группе — по триггер-слову или если ответили боту
    if message.chat.type in ("group", "supergroup"):
        if not message.text:
            return False

        # Если в сообщении есть "бурмалда"
        if TRIGGER_WORD.lower() in message.text.lower():
            return True

        # Если это ответ (Reply) на сообщение бота
        if message.reply_to_message and message.reply_to_message.from_user:
            if message.reply_to_message.from_user.id == message.bot.id:
                return True

        return False

    # Другие типы чатов (канал и т.д.) — игнорируем
    return False


@router.message()
async def ai_message(message: Message) -> None:
    """
    Обрабатывает текстовые сообщения:
    - ЛС: отвечает на всё
    - Группа: только по ключевому слову
    """
    if not message.text:
        return

    # Проверяем, нужно ли отвечать
    if not _should_respond(message):
        return

    user_id = message.from_user.id
    user_text = message.text.strip()

    # В группах вырезаем слово "бурмалда" из текста перед отправкой AI
    if message.chat.type in ("group", "supergroup"):
        # Удаляем триггер-слово (регистронезависимо)
        import re
        user_text = re.sub(re.escape(TRIGGER_WORD), "", user_text, flags=re.IGNORECASE)
        # Чистим от лишних знаков препинания и пробелов
        user_text = user_text.strip(" ,.!?:;-\n").strip()

    if not user_text:
        return

    # Показываем, что бот печатает
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        # Спрашиваем LLM
        answer = await ask_llm(user_id, user_text)

        # Отправляем с Markdown (чтобы ```-блоки отображались как код).
        # Если Telegram не примет разметку — отправляем обычным текстом.
        try:
            await message.reply(answer, parse_mode="Markdown")
        except Exception:
            await message.reply(answer, parse_mode=None)

    except Exception as e:
        logger.exception(f"Ошибка при обработке сообщения от {user_id}")
        await message.reply(
            "😔 Произошла ошибка при обработке запроса. "
            "Попробуй ещё раз или напиши /clear чтобы сбросить диалог.\n\n"
            f"<code>{type(e).__name__}: {e}</code>",
            parse_mode="HTML",
        )
