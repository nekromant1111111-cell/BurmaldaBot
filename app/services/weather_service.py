"""Погода через бесплатный open-meteo API (без ключа)."""

import logging
import re

import aiohttp

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Коды WMO -> русское описание
_WMO = {
    0: "ясно",
    1: "преимущественно ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь",
    51: "лёгкая морось",
    53: "морось",
    55: "сильная морось",
    61: "небольшой дождь",
    63: "дождь",
    65: "сильный дождь",
    71: "небольшой снег",
    73: "снег",
    75: "сильный снег",
    80: "ливень",
    81: "ливень",
    82: "сильный ливень",
    95: "гроза",
    96: "гроза с градом",
    99: "гроза с градом",
}


def _extract_city(text: str) -> str:
    """Достаёт название города из запроса. Если не понятно — Москва."""
    cleaned = text.lower()
    cleaned = re.sub(r"погод\w*", "", cleaned)
    cleaned = re.sub(
        r"\bкакая\b|\bкакой\b|\bсейчас\b|\bсегодня\b|\bзавтра\b|\bвчера\b"
        r"|\bв\b|\bна\b|\bнад\b|\bво\b|\bпо\b|\bкак\b|\bбудет\b|\bстоит\b"
        r"|\bнеделю\b|\bнеделе\b|\bднем\b|\bвечером\b|\bутром\b|\bночью\b"
        r"|\bградус\w*\b|\bтемпература\w*\b|\bтепло\b|\bхолод\w*\b|\bмороз\w*\b",
        " ",
        cleaned,
    )
    cleaned = re.sub(r"[^а-яёa-z\s\-]", " ", cleaned)
    city = cleaned.strip().title()
    if not (2 <= len(city) <= 30):
        return "Москва"
    return city


async def get_weather_text(query: str) -> str | None:
    """Возвращает текст с погодой или None, если не получилось."""
    city = _extract_city(query)
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Геокодинг: город -> координаты
            async with session.get(
                GEOCODING_URL,
                params={"name": city, "count": 1, "language": "ru"},
                timeout=10,
            ) as resp:
                if resp.status != 200:
                    return None
                geo = await resp.json()

            results = geo.get("results") or []
            if not results:
                return None

            lat = results[0]["latitude"]
            lon = results[0]["longitude"]
            name = results[0]["name"]

            # 2. Текущая погода по координатам
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "timezone": "Europe/Moscow",
            }
            async with session.get(FORECAST_URL, params=params, timeout=10) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
    except Exception as e:
        logger.error(f"Ошибка погоды: {e}")
        return None

    cur = data.get("current", {})
    temp = cur.get("temperature_2m")
    if temp is None:
        return None

    hum = cur.get("relative_humidity_2m")
    wind = cur.get("wind_speed_10m")
    code = cur.get("weather_code")
    desc = _WMO.get(code, "переменная погода")

    lines = [f"🌤 Погода сейчас в {name}:"]
    lines.append(f"• Температура: {temp}°C")
    lines.append(f"• Состояние: {desc}")
    if hum is not None:
        lines.append(f"• Влажность: {hum}%")
    if wind is not None:
        lines.append(f"• Ветер: {wind} км/ч")
    return "\n".join(lines)
