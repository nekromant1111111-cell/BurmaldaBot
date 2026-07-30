"""
AI-сервис: общение с Google Gemini + инструменты (поиск, курс валют, чтение страниц).

Gemini 3.5 Flash Lite — бесплатно, 60 запросов в минуту.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Literal

from google import genai
from google.genai import types as genai_types

from config import Config

logger = logging.getLogger(__name__)

# Типы ролей
Role = Literal["user", "model"]

# Словарь для хранения истории диалогов
_chat_history: dict[int, list[genai_types.Content]] = {}

# ———— Инструменты (tools) для Gemini ———— #

SEARCH_TOOL = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="web_search",
            description="Поиск в интернете. Используй когда нужно найти свежую информацию, новости, факты.",
            parameters=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "query": genai_types.Schema(
                        type=genai_types.Type.STRING,
                        description="Поисковый запрос.",
                    ),
                },
                required=["query"],
            ),
        )
    ]
)

CURRENCY_TOOL = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="get_currency_rate",
            description="Получить официальный курс валют к рублю от Центробанка РФ (USD, EUR, CNY и др.)",
            parameters=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={},
            ),
        )
    ]
)

READ_URL_TOOL = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="read_url",
            description="Прочитать содержимое страницы по URL-ссылке.",
            parameters=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "url": genai_types.Schema(
                        type=genai_types.Type.STRING,
                        description="Полный URL страницы.",
                    ),
                },
                required=["url"],
            ),
        )
    ]
)

TOOLS = [SEARCH_TOOL, CURRENCY_TOOL, READ_URL_TOOL]


def _gemini_client() -> genai.Client:
    return genai.Client(api_key=Config.GEMINI_API_KEY)


def get_history(user_id: int) -> list[genai_types.Content]:
    return _chat_history.get(user_id, [])


def _trim_history(user_id: int) -> None:
    history = _chat_history.get(user_id, [])
    max_msgs = Config.MAX_HISTORY
    if len(history) > max_msgs:
        _chat_history[user_id] = history[-max_msgs:]


def add_message(user_id: int, role: str, text: str) -> None:
    if user_id not in _chat_history:
        _chat_history[user_id] = []
    _chat_history[user_id].append(
        genai_types.Content(role=role, parts=[genai_types.Part.from_text(text=text)])
    )
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


async def ask_gemini(user_id: int, message: str) -> str:
    """
    Отправить сообщение Gemini с историей и инструментами.
    """
    client = _gemini_client()
    model = Config.GEMINI_MODEL

    msk_tz = timezone(timedelta(hours=3))
    system = SYSTEM_PROMPT.format(
        current_date=datetime.now(msk_tz).strftime("%d.%m.%Y %H:%M (МСК)")
    )

    history = get_history(user_id)
    contents = list(history)
    contents.append(
        genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=message)])
    )

    for _ in range(10):
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                tools=TOOLS,
                system_instruction=system,
                temperature=0.7,
            ),
        )

        if not response.candidates:
            return "Ответ заблокирован фильтрами. Попробуй переформулировать."

        part = response.candidates[0].content.parts[0]

        if part.function_call:
            fc = part.function_call
            tool_name = fc.name
            tool_args = {k: v for k, v in fc.args.items()}
            logger.info(f"Юзер {user_id} -> {tool_name}({tool_args})")

            result = await _run_tool(tool_name, tool_args)
            contents.append(response.candidates[0].content)
            contents.append(
                genai_types.Content(
                    role="user",
                    parts=[
                        genai_types.Part.from_function_response(
                            name=tool_name,
                            response={"result": result},
                        )
                    ],
                )
            )
            continue

        if part.text:
            answer = part.text
            add_message(user_id, "user", message)
            add_message(user_id, "model", answer)
            return answer

        return "(пусто)"

    return "Слишком много итераций. Уточни запрос."
