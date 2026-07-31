"""
AI-сервис: общение с DeepSeek v4 Flash (через Yandex Cloud API) + инструменты.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Literal

from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)

# Типы ролей для истории
Role = Literal["user", "assistant"]

# Словарь для хранения истории диалогов: user_id -> список сообщений
_chat_history: dict[int, list[dict]] = {}

# ———— Инструменты (tools) в OpenAI-формате ———— #

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Поиск в интернете. Используй когда нужно найти свежую информацию, новости, факты.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос.",
                },
            },
            "required": ["query"],
        },
    },
}

READ_URL_TOOL = {
    "type": "function",
    "function": {
        "name": "read_url",
        "description": "Прочитать содержимое страницы по URL-ссылке.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Полный URL страницы.",
                },
            },
            "required": ["url"],
        },
    },
}

CURRENCY_TOOL = {
    "type": "function",
    "function": {
        "name": "get_currency_rate",
        "description": "Получить официальный курс валют к рублю от Центробанка РФ (USD, EUR, CNY и др.)",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

TOOLS = [WEB_SEARCH_TOOL, READ_URL_TOOL, CURRENCY_TOOL]


def _llm_client() -> OpenAI:
    """Создаёт клиент LLM API (совместимый с OpenAI)."""
    return OpenAI(
        api_key=Config.LLM_API_KEY,
        base_url=Config.LLM_BASE_URL,
    )


def get_history(user_id: int) -> list[dict]:
    return _chat_history.get(user_id, [])


def _trim_history(user_id: int) -> None:
    history = _chat_history.get(user_id, [])
    max_msgs = Config.MAX_HISTORY
    if len(history) > max_msgs:
        _chat_history[user_id] = history[-max_msgs:]


def add_message(user_id: int, role: str, content: str) -> None:
    if user_id not in _chat_history:
        _chat_history[user_id] = []
    _chat_history[user_id].append({"role": role, "content": content})
    _trim_history(user_id)


def clear_history(user_id: int) -> None:
    _chat_history.pop(user_id, None)


# ———— Инструменты (обработчики) ———— #


async def _web_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))

        if not results:
            return "Ничего не найдено."

        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "Без заголовка")
            snippet = r.get("body", "")
            href = r.get("href", "")
            lines.append(f"{i}. {title}\n   {snippet}\n   {href}")

        return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return f"Не удалось выполнить поиск: {e}"


async def _read_url(url: str) -> str:
    try:
        import aiohttp
        from bs4 import BeautifulSoup

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    return f"Ошибка HTTP {resp.status}"
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)[:5000]
        return text or "Пустая страница."
    except Exception as e:
        return f"Не удалось прочитать страницу: {e}"


async def _get_currency_rate() -> str:
    try:
        import aiohttp
        import json as json_mod

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.cbr-xml-daily.ru/daily_json.js", timeout=10
            ) as resp:
                if resp.status != 200:
                    return f"Ошибка HTTP {resp.status}"
                data = json_mod.loads(await resp.text())

        valutes = data.get("Valute", {})
        lines = ["Курсы валют ЦБ РФ:"]
        for code in ["USD", "EUR", "CNY", "KZT", "TRY"]:
            v = valutes.get(code)
            if v:
                value = v.get("Value", "?") / v.get("Nominal", 1)
                lines.append(f"  {code}: {value:.2f} руб")

        date = data.get("Date", "")
        if date:
            lines.append(f"Обновлено: {date[:10]}")
        return "\n".join(lines)
    except Exception as e:
        return f"Не удалось получить курс: {e}"


async def _run_tool(name: str, args: dict) -> str:
    if name == "web_search":
        return await _web_search(args.get("query", ""))
    elif name == "read_url":
        return await _read_url(args.get("url", ""))
    elif name == "get_currency_rate":
        return await _get_currency_rate()
    else:
        return f"Неизвестный инструмент: {name}"


SYSTEM_PROMPT = """Ты — умный AI-ассистент в Telegram. Тебя зовут Бурмалда. Отвечай на русском языке.

ТВОЙ СТИЛЬ: как опытный эксперт, который даёт развёрнутые ответы с фактами и примерами. Не будь поверхностным.

ИСПОЛЬЗУЙ ИНСТРУМЕНТЫ:
- web_search — для поиска в интернете (новости, факты, информация, цены)
- get_currency_rate — для курса валют ЦБ РФ
- read_url — для чтения страниц по ссылкам

ВАЖНО: Текущее время и дата уже указаны в начале промпта, НЕ вызывай web_search для вопроса о времени.
Если вопрос про актуальные данные (новости, курсы, погоду) — сразу ищи в интернете.

ВАЖНО: НЕ используй символы разметки (*, #, _, >, `). Telegram показывает их как мусор. Используй обычный текст, ЗАГЛАВНЫЕ для выделения.

Региональные настройки: рубли (₽), МСК (UTC+3), метрическая система, русский язык, даты ДД.ММ.ГГГГ.

Сейчас в Москве: {current_date}
"""


async def ask_llm(user_id: int, message: str) -> str:
    """
    Отправить сообщение модели с историей и инструментами.
    """
    client = _llm_client()
    model = Config.LLM_MODEL

    msk_tz = timezone(timedelta(hours=3))
    system = SYSTEM_PROMPT.format(
        current_date=datetime.now(msk_tz).strftime("%d.%m.%Y %H:%M (МСК)")
    )

    history = get_history(user_id)
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    # Максимум 10 итераций вызовов инструментов
    for _ in range(10):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                temperature=0.7,
                max_tokens=4096,
            )
        except Exception as e:
            logger.error(f"Ошибка LLM API: {e}")
            raise

        choice = response.choices[0]
        msg = choice.message

        # Если модель вызвала инструменты
        if msg.tool_calls:
            messages.append(msg)

            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info(f"Юзер {user_id} -> {tool_name}({tool_args})")
                result = await _run_tool(tool_name, tool_args)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

            continue

        # Текстовый ответ
        if msg.content:
            answer = msg.content
            add_message(user_id, "user", message)
            add_message(user_id, "assistant", answer)
            return answer

        return "(пусто)"

    return "Слишком много итераций. Уточни запрос."
