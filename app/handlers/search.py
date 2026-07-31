"""Поиск в интернете через DuckDuckGo с защитой от перегрузки.

Бот сам следит за своими ресурсами:
- лимит запросов в минуту на пользователя
- ограничение одновременных поисков
- таймаут, чтобы не зависнуть
- кэш, чтобы повторные запросы не били в API
- авто-пауза, если поисковик начал отдавать ошибки
"""

import asyncio
import logging
import time

from aiogram import Router
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()

# Настройки защиты
MAX_SEARCHES_PER_MINUTE = 3   # запросов в минуту на пользователя
MAX_CONCURRENT = 2            # одновременных поисков по всему боту
SEARCH_TIMEOUT = 12           # секунд на один поиск (дольше — отменяем)
CACHE_TTL = 300               # кэшировать результаты 5 минут
MAX_RESULTS = 5               # сколько результатов показывать
MAX_FAILURES = 3              # больше ошибок за минуту -> пауза
FAILURE_WINDOW = 60           # секунд, окно для подсчёта ошибок

# Внутреннее состояние
_semaphore = asyncio.Semaphore(MAX_CONCURRENT)
_user_searches: dict[int, list[float]] = {}
_cache: dict[str, tuple[float, str]] = {}
_failures: list[float] = []


def _search_pause() -> int:
    """Сколько секунд осталось до конца паузы (0 = можно искать)."""
    now = time.time()
    recent = [t for t in _failures if now - t < FAILURE_WINDOW]
    if len(recent) >= MAX_FAILURES:
        return int(FAILURE_WINDOW - (now - max(recent)))
    return 0


def _record_success() -> None:
    """Поиск удался — сбрасываем копилку ошибок."""
    _failures.clear()


def _record_failure() -> None:
    """Поиск упал — запоминаем."""
    now = time.time()
    _failures.append(now)
    _failures[:] = [t for t in _failures if now - t < FAILURE_WINDOW]


async def _do_search(query: str) -> list[dict]:
    """Выполняет поиск в фоновом потоке с таймаутом."""
    from duckduckgo_search import DDGS

    def _run() -> list[dict]:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=MAX_RESULTS, region="ru-ru"))

    return await asyncio.wait_for(
        asyncio.to_thread(_run),
        timeout=SEARCH_TIMEOUT,
    )


def _format_results(query: str, results: list[dict]) -> str:
    """Форматирует результаты. Отправка идёт без Markdown, чтобы ссылки были кликабельными."""
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


def _extract_query(message: Message) -> str | None:
    """Достаёт текст запроса из команды вида: /поиск что искать"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return None
    return parts[1].strip()


async def _run_search(message: Message, query: str) -> None:
    user_id = message.from_user.id

    # 1. Проверяем глобальную паузу (поисковик злится — отдыхаем)
    pause = _search_pause()
    if pause > 0:
        await message.answer(
            f"😴 Поиск временно отдыхает (проблемы с сервером). "
            f"Попробуй через {pause} сек.",
            parse_mode=None,
        )
        return

    # 2. Проверяем личный лимит пользователя
    now = time.time()
    window = now - 60
    lst = [t for t in _user_searches.get(user_id, []) if t > window]
    if len(lst) >= MAX_SEARCHES_PER_MINUTE:
        wait = int(60 - (now - min(lst)))
        await message.answer(
            f"⏳ Слишком часто. Следующий поиск можно через {wait} сек.",
            parse_mode=None,
        )
        return
    lst.append(now)
    _user_searches[user_id] = lst

    # 3. Проверяем кэш — повторный запрос отдаём без обращения к API
    cache_key = query.lower()
    cached = _cache.get(cache_key)
    if cached and now - cached[0] < CACHE_TTL:
        await message.answer(cached[1], parse_mode=None)
        return

    # 4. Ищем (с семафором и таймаутом)
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    try:
        async with _semaphore:
            results = await _do_search(query)
    except asyncio.TimeoutError:
        _record_failure()
        await message.answer(
            "⏱ Поиск занял слишком много времени. Попробуй ещё раз.",
            parse_mode=None,
        )
        return
    except Exception as e:
        _record_failure()
        logger.error(f"Ошибка поиска для {user_id}: {e}")
        await message.answer(
            "😔 Поиск временно недоступен. Попробуй позже или уточни запрос.",
            parse_mode=None,
        )
        return

    if not results:
        await message.answer("🤷 Ничего не нашёл по этому запросу.", parse_mode=None)
        return

    _record_success()
    text = _format_results(query, results)
    _cache[cache_key] = (time.time(), text)
    await message.answer(text, parse_mode=None)


def is_search_cmd(message: Message) -> bool:
    """Фильтр: сообщение начинается с /поиск или /search (с или без @имябота)."""
    text = message.text or ""
    if not text:
        return False
    first = text.split(maxsplit=1)[0]
    cmd = first.split("@")[0].lower()
    return cmd in ("/поиск", "/search")


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
    await _run_search(message, query)
