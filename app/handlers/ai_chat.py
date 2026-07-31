"""Основной хендлер: AI-чат.

Правила:
- В личном чате — отвечает на всё
- В группе — только если в сообщении есть слово "бурмалда"
"""

import logging

from aiogram import Router
from aiogram.types import Message

from app.services.ai_service import add_message, ask_llm, get_history
from app.services import search_service

logger = logging.getLogger(__name__)

router = Router()

# Ключевое слово для активации в группах
TRIGGER_WORD = "бурмалда"

# Лимит символов в одном сообщении Telegram (4096). Берём с запасом.
MAX_MSG_LEN = 3950


def _split_text(text: str, max_len: int = MAX_MSG_LEN) -> list[str]:
    """Разбивает длинный текст на части, стараясь не разрывать код-блоки."""
    if len(text) <= max_len:
        return [text]

    lines = text.split("\n")
    parts: list[str] = []
    current = ""
    in_code = False

    for line in lines:
        stripped = line.strip()
        # Строка открывает/закрывает код-блок?
        if stripped.startswith("```"):
            # Открывающий блок не влезает в текущую часть — закрываем часть
            if not in_code and current and len(current) + len(line) + 1 > max_len:
                parts.append(current.rstrip("\n"))
                current = ""
            # Блок уже идёт, а очередной блок не влезает — закрываем блок в части
            elif in_code and current and len(current) + len(line) + 1 > max_len:
                parts.append(current.rstrip("\n") + "\n```")
                current = "```\n"  # открываем блок заново
            in_code = not in_code
            current += line + "\n"
            continue

        # Обычная строка
        if len(current) + len(line) + 1 > max_len:
            if current:
                if in_code:
                    # закрываем код-блок в конце части
                    parts.append(current.rstrip("\n") + "\n```")
                    current = "```\n"
                else:
                    parts.append(current.rstrip("\n"))
                    current = ""
            # Если одна строка длиннее лимита — режем её по кускам
            while len(line) > max_len:
                parts.append(line[:max_len])
                line = line[max_len:]
        current += line + "\n"

    if current:
        if in_code:
            current += "```"
        parts.append(current.rstrip("\n"))

    return parts


async def _send_answer(message: Message, answer: str) -> None:
    """Отправляет ответ, разбивая на части если нужно."""
    for part in _split_text(answer):
        # Пробуем с Markdown (чтобы ```-блоки отображались как код).
        # Если Telegram не примет разметку — отправляем обычным текстом.
        try:
            await message.reply(part, parse_mode="Markdown")
        except Exception:
            await message.reply(part, parse_mode=None)


def _is_ai_message(message: Message) -> bool:
    """Фильтр: обычное сообщение (не команда)."""
    if not message.text:
        return False
    return not message.text.startswith("/")


# Слова-подсказки (границы слов, чтобы "курс" не срабатывал в слове "рекурсия")
_SEARCH_WORDS = (
    r"\bновост", r"\bкурс", r"\bпогод", r"\bцена", r"\bцене", r"\bстоимост",
    r"\bактуальн", r"\bпоследн", r"\bсвеж", r"\bпроисходит", r"\bслучил",
    r"\bрелиз", r"\bдоллар", r"\bевро", r"\bюань", r"\bбиткоин", r"\bbitcoin",
    r"\bbtc", r"\busd", r"\beur", r"\bпрезидент", r"\bвыборы", r"\bсанкци",
    r"\bчемпионат", r"\bтурнир", r"\bматч",
)

# Многословные фразы (обычное вхождение)
_SEARCH_PHRASES = (
    "сколько стоит", "какой курс", "что слышно", "что нового", "что сейчас",
    "выход фильм", "выход игры", "результат игр", "цена на",
)


def _needs_search(text: str) -> bool:
    """Эвристика: похоже ли сообщение на запрос свежей информации."""
    import re
    t = text.lower()
    if any(p in t for p in _SEARCH_PHRASES):
        return True
    return any(re.search(p, t) for p in _SEARCH_WORDS)


def _format_search_context(query: str, results: list[dict]) -> str:
    """Форматирует результаты поиска как контекст для модели."""
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "Без заголовка")
        body = r.get("body", "")
        href = r.get("href", "")
        lines.append(f"{i}. {title}")
        if body:
            lines.append(f"   {body[:200]}")
        lines.append(f"   Источник: {href}")
    return "\n".join(lines)


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


@router.message(_is_ai_message)
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
        # Автопоиск: если вопрос похож на запрос свежих данных — ищем в интернете
        search_context = None
        if _needs_search(user_text):
            await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
            ok, result = await search_service.search(user_id, user_text)
            if ok and result:
                search_context = _format_search_context(user_text, result)
                logger.info(f"Автопоиск для {user_id}: найдено {len(result)} результатов")

        # Спрашиваем LLM (с результатами поиска, если они есть)
        answer = await ask_llm(user_id, user_text, search_context=search_context)

        # Отправляем ответ (разбивая на части, если длинный)
        await _send_answer(message, answer)

    except Exception as e:
        logger.exception(f"Ошибка при обработке сообщения от {user_id}")
        await message.reply(
            "😔 Произошла ошибка при обработке запроса. "
            "Попробуй ещё раз или напиши /clear чтобы сбросить диалог.\n\n"
            f"<code>{type(e).__name__}: {e}</code>",
            parse_mode="HTML",
        )
