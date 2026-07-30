FROM python:3.12-slim

WORKDIR /app

COPY . .

# Шаг 1: ставим google-genai с его зависимостями (включая pydantic 2.13+)
RUN pip install --no-cache-dir google-genai

# Шаг 2: ставим aiogram без проверки зависимостей (он работает с pydantic 2.13 на.runtime)
RUN pip install --no-cache-dir --no-deps aiogram==3.17.0

# Шаг 3: ставим зависимости aiogram которые не конфликтуют
RUN pip install --no-cache-dir \
    aiofiles==24.1.0 \
    aiohttp==3.11.12 \
    aiohttp-socks==0.11.0 \
    aiohappyeyeballs==2.7.1 \
    aiosignal==1.4.0 \
    attrs==26.1.0 \
    frozenlist==1.8.0 \
    multidict==6.7.1 \
    propcache==0.5.2 \
    yarl==1.24.5 \
    magic-filter==1.0.12 \
    python-dotenv==1.1.0 \
    beautifulsoup4==4.13.3 \
    duckduckgo-search==8.1.1 \
    python-socks==2.8.2 \
    soupsieve==2.9.1 \
    certifi \
    idna

EXPOSE 8080

CMD ["python", "bot.py"]
