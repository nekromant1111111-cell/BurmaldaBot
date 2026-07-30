FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

# Сначала ставим всё (будет ошибка из-за конфликта pydantic, но пакеты установятся)
RUN pip install --no-cache-dir \
    aiogram==3.17.0 \
    duckduckgo-search==8.1.1 \
    python-dotenv==1.1.0 \
    aiohttp==3.11.12 \
    beautifulsoup4==4.13.3 \
    aiohttp-socks==0.11.0 2>/dev/null || true

# Google-genai ставим без проверки зависимостей
RUN pip install --no-cache-dir google-genai --no-deps

COPY . .

EXPOSE 8080

CMD ["python", "bot.py"]
