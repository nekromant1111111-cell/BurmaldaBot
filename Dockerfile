FROM python:3.12-slim

WORKDIR /app

COPY . .

# Ставим google-genai первым (подтянет pydantic 2.12+, httpx и т.д.)
RUN pip install --no-cache-dir google-genai

# Ставим остальное без проверки зависимостей (aiogram конфликтует по pydantic, но работает)
RUN pip install --no-cache-dir --no-deps \
    aiogram==3.17.0 \
    aiofiles==24.1.0 \
    aiohttp==3.11.12 \
    aiohttp-socks==0.11.0 \
    aiohappyeyeballs==2.7.1 \
    aiosignal==1.4.0 \
    magic-filter==1.0.12 \
    python-dotenv==1.1.0 \
    beautifulsoup4==4.13.3 \
    duckduckgo-search==8.1.1 \
    python-socks==2.8.2 \
    soupsieve==2.9.1

EXPOSE 8080

CMD ["python", "bot.py"]
