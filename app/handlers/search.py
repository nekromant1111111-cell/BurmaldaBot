"""Команда /поиск — явный поиск в интернете.

Сама логика и защита от перегрузки живут в app/services/search_service.py.
"""

import logging

from aiogram import Router
from aiogram.types import Message

from app.services import search_service

logger = logging.getLogger(__name__)

router = Router()


def is_search_cmd(message: Message) -> bool:
    """Фильтр: сообщение начинается с /поиск или /search (с или без @имябота)."""
    text = message.text or ""
    if not text:
        return False
    first = text.split(maxsplit=1)[0]
    cmd = first.split("@")[0].lower()
    return cmd in ("/поиск", "/search")


def _extract_query(message: Message) -> str | None:
    """Достаёт текст запроса из команды вида: /поиск что искать"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return None
    return parts[1].strip()


def _format_results(query: str, results: list[dict]) -> str:
    """Форматирует результаты. Отправка без Markdown, чтобы ссылки были кликабельными."""
    lines = [f"🔍 Результаты по запросу: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "Без заголовка")
        body = r.get("body", "")
        href = r.get("href", "")
        lines.append(f"{i}. {title}")
        if body:
            lines.append(f"   {body[:160]}")
        lines.append(f"   {href}")
    return "\n".join(lines)


def _reason_message(reason: str) -> str:
    if reason == "pause":
        return "😴 Поиск временно отдыхает (проблемы с сервером). Попробуй чуть позже."
    if reason == "cooldown":
        wait = search_service.user_cooldown_seconds(0)  # просто для текста
        return f"⏳ Слишком часто. Подожди немного (до {wait} сек)."
    if reason == "timeout":
        return "⏱ Поиск занял слишком много времени. Попробуй ещё раз."
    return "😔 Поиск временно недоступен. Попробуй позже."


@router.message(is_search_cmd)
async def search_handler(message: Message) -> None:
    """Обработчик /поиск запрос"""
    query = _extract_query(message)
    if not query:
        await message.answer(
            "🔍 Напиши запрос после команды, например:\n"
            "/поиск новости про ИИ сегодня",
            parse_mode=None,
        )
        return

    ok, result = await search_service.search(message.from_user.id, query)
    if not ok:
        await message.answer(_reason_message(result), parse_mode=None)
        return
    if not result:
        await message.answer("🤷 Ничего не нашёл по этому запросу.", parse_mode=None)
        return

    await message.answer(_format_results(query, result), parse_mode=None)
