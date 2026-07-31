import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Конфигурация бота из переменных окружения."""

    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # LLM (OpenRouter)
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")

    # Настройки диалога
    MAX_HISTORY: int = int(os.getenv("MAX_HISTORY", "20"))

    # Webhook / Polling
    USE_WEBHOOK: bool = os.getenv("USE_WEBHOOK", "False").lower() == "true"
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_PORT: int = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8080")))

    # Хост для вебхука (0.0.0.0 для Render)
    WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")

    @classmethod
    def validate(cls) -> list[str]:
        """Проверяет, что все необходимые переменные заданы."""
        errors: list[str] = []
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN не задан! Получи его у @BotFather")
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY не задан!")
        return errors
