import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Конфигурация бота из переменных окружения."""

    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Google Gemini API (бесплатно до 60 запросов/мин)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    # Настройки диалога
    MAX_HISTORY: int = int(os.getenv("MAX_HISTORY", "20"))

    # Webhook / Polling
    USE_WEBHOOK: bool = os.getenv("USE_WEBHOOK", "False").lower() == "true"
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8080"))

    # Хост для вебхука (0.0.0.0 для Render)
    WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")

    @classmethod
    def validate(cls) -> list[str]:
        """Проверяет, что все необходимые переменные заданы."""
        errors: list[str] = []
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN не задан! Получи его у @BotFather")
        if not cls.GEMINI_API_KEY:
            errors.append(
                "GEMINI_API_KEY не задан! Получи ключ бесплатно на "
                "https://aistudio.google.com/apikey"
            )
        return errors
