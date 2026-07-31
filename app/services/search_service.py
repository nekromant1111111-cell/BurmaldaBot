"""Ядро поиска в интернете с защитой от перегрузки.

Используется и командой /поиск, и автоматическим поиском.
Бот сам следит за ресурсами:
- лимит запросов в минуту на пользователя
- ограничение одновременных поисков
- таймаут, чтобы не зависнуть
- кэш, чтобы повторные запросы не били в API
- авто-пауза, если поисковик начал отдавать ошибки
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

# Настройки защиты
MAX_SEARCHES_PER_MINUTE = 3   # запросов в минуту на пользователя
MAX_CONCURRENT = 2            # одновременных поисков по всему боту
SEARCH_TIMEOUT = 12           # секунд на один поиск (дольше — отменяем)
CACHE_TTL = 300               # кэшировать результаты 5 минут
MAX_RESULTS = 5               # сколько результатов брать
MAX_FAILURES = 3              # больше ошибок за минуту -> пауза
FAILURE_WINDOW = 60           # секунд, окно для подсчёта ошибок

# Внутреннее состояние
_semaphore = asyncio.Semaphore(MAX_CONCURRENT)
_user_searches: dict[int, list[float]] = {}
_cache: dict[str, tuple[float, list[dict]]] = {}
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


def search_pause_seconds() -> int:
    """Секунд до конца глобальной паузы (0 = можно)."""
    return _search_pause()


def user_cooldown_seconds(user_id: int) -> int:
    """Секунд до следующего поиска для пользователя (0 = можно)."""
    now = time.time()
    lst = [t for t in _user_searches.get(user_id, []) if t > now - 60]
    if len(lst) >= MAX_SEARCHES_PER_MINUTE:
        return int(60 - (now - min(lst)))
    return 0


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


async def search(user_id: int, query: str) -> tuple[bool, list[dict] | str]:
    """
    Ищет с защитой от перегрузки.

    Возвращает (True, список результатов) при успехе,
    или (False, код причины): "pause", "cooldown", "timeout", "error".
    """
    if _search_pause() > 0:
        return False, "pause"
    if user_cooldown_seconds(user_id) > 0:
        return False, "cooldown"

    now = time.time()
    _user_searches.setdefault(user_id, []).append(now)

    # Кэш: повторный запрос отдаём без обращения к API
    cache_key = query.strip().lower()
    cached = _cache.get(cache_key)
    if cached and now - cached[0] < CACHE_TTL:
        return True, cached[1]

    try:
        async with _semaphore:
            results = await _do_search(query)
    except asyncio.TimeoutError:
        _record_failure()
        return False, "timeout"
    except Exception as e:
        _record_failure()
        logger.error(f"Ошибка поиска: {e}")
        return False, "error"

    if not results:
        return True, []

    _record_success()
    _cache[cache_key] = (time.time(), results)
    return True, results
