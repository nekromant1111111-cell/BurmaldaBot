"""
Точка входа Telegram AI-бота.

Поддерживает два режима:
- Polling (локальная разработка)
- Webhook (для Railway / Render)
"""

from __future__ import annotations

import logging
import os
import sys
from urllib.request import getproxies

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import Config
from app.handlers import start, ai_chat, search

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _get_proxy() -> str | None:
    """Определяет системный прокси для aiohttp (если есть)."""
    proxies = getproxies()
    # Берём HTTPS прокси (или HTTP как запасной)
    return proxies.get("https") or proxies.get("http") or None


def _create_bot() -> Bot:
    """Создаёт бота с учётом системного прокси."""
    proxy = _get_proxy()
    if proxy:
        logger.info(f"Обнаружен системный прокси: {proxy}")
        # Используем aiohttp сессию с прокси
        session = AiohttpSession(proxy=proxy)
        return Bot(
            token=Config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
            session=session,
        )
    else:
        return Bot(
            token=Config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        )


async def on_startup(bot: Bot) -> None:
    """Действия при запуске: установка вебхука."""
    if Config.USE_WEBHOOK:
        base = Config.WEBHOOK_URL or os.getenv("RENDER_EXTERNAL_URL", "")
        if not base:
            logger.error("WEBHOOK_URL не задан! Не могу установить webhook")
            return
        webhook_url = f"{base}/webhook"
        await bot.set_webhook(webhook_url)
        logger.info(f"Webhook установлен: {webhook_url}")
    else:
        # Удаляем вебхук на случай если он был
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Вебхук удалён, работаем в режиме polling")


async def on_shutdown(bot: Bot) -> None:
    """Действия при остановке: ничего не удаляем, чтобы webhook оставался."""
    logger.info("Бот останавливается... webhook сохраняется")


def create_dispatcher() -> Dispatcher:
    """Создаёт и настраивает диспетчер."""
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрируем роутеры (search — до ai_chat, чтобы команда не уходила в AI)
    dp.include_router(start.router)
    dp.include_router(search.router)
    dp.include_router(ai_chat.router)

    return dp


def start_polling() -> None:
    """Запуск в режиме polling."""
    bot = _create_bot()
    dp = create_dispatcher()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Бот запущен в режиме polling")
    dp.run_polling(bot)


def start_webhook() -> None:
    """Запуск в режиме webhook (для Render/Railway)."""
    bot = _create_bot()
    dp = create_dispatcher()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()

    # Health check — чтобы Render не засыпал
    async def health(request):
        return web.Response(text="BurmaldaBot is alive!")

    app.router.add_get("/", health)

    # Настраиваем вебхук
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")

    setup_application(app, dp, bot=bot)

    logger.info(f"Бот запущен в режиме webhook на порту {Config.WEBHOOK_PORT}")
    web.run_app(app, host=Config.WEBHOOK_HOST, port=Config.WEBHOOK_PORT)


def main() -> None:
    """Точка входа."""
    # Проверяем конфигурацию
    errors = Config.validate()
    if errors:
        logger.error("Ошибки конфигурации:")
        for err in errors:
            logger.error(f"  ❌ {err}")
        sys.exit(1)

    # Автоопределение Render: если есть PORT — это Render, включаем webhook
    # даже если USE_WEBHOOK не задан в переменных
    if os.getenv("PORT"):
        Config.USE_WEBHOOK = True
        if not Config.WEBHOOK_URL:
            Config.WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL", "")

    logger.info(f"AI-бот запускается... Режим: {'webhook' if Config.USE_WEBHOOK else 'polling'}")
    logger.info(f"Модель: {Config.LLM_MODEL} (OpenRouter)")

    if Config.USE_WEBHOOK:
        start_webhook()
    else:
        start_polling()


if __name__ == "__main__":
    main()
