"""Случайный мем из папки memes.

Команды: /мем, /шутка, /анекдот
А также авто-реакция, когда пользователь просит шутку словами.
"""

import logging
import random
from pathlib import Path

from aiogram import Router
from aiogram.types import FSInputFile, Message

logger = logging.getLogger(__name__)

router = Router()

# Папка с мемами (в корне проекта)
MEMES_DIR = Path(__file__).resolve().parents[2] / "memes"

# Поддерживаемые форматы картинок
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

# Команды
_MEME_COMMANDS = ("/мем", "/шутка", "/анекдот", "/мемчик")

# Слова-триггеры для авто-реакции
_MEME_HINTS = ("шутк", "мем", "анекдот", "рассмеши", "пошути", "мемчик")


def _is_command(message: Message) -> bool:
    """Начинается ли сообщение с команды мема (с или без @имябота)."""
    text = message.text or ""
    if not text:
        return False
    first = text.split(maxsplit=1)[0]
    cmd = first.split("@")[0].lower()
    return cmd in _MEME_COMMANDS


def is_meme_request(message: Message) -> bool:
    """Фильтр: обычное сообщение, просьба показать мем/шутку."""
    text = message.text or ""
    if not text or text.startswith("/"):
        return False
    t = text.lower()
    return any(h in t for h in _MEME_HINTS)


def _list_memes() -> list[Path]:
    """Список картинок в папке memes."""
    if not MEMES_DIR.exists():
        return []
    return [p for p in MEMES_DIR.iterdir() if p.suffix.lower() in _IMAGE_EXTS]


async def _send_random_meme(message: Message) -> None:
    memes = _list_memes()
    if not memes:
        await message.answer(
            "😅 Папка с мемами пуста. Добавь картинки в папку memes бота!",
            parse_mode=None,
        )
        return

    chosen = random.choice(memes)
    try:
        if chosen.suffix.lower() == ".gif":
            await message.answer_animation(
                FSInputFile(str(chosen)), caption="😄 Держи!"
            )
        else:
            await message.answer_photo(FSInputFile(str(chosen)), caption="😄 Держи мем!")
    except Exception as e:
        logger.error(f"Ошибка отправки мема {chosen}: {e}")
        await message.answer("😔 Не удалось отправить мем.", parse_mode=None)


@router.message(_is_command)
async def cmd_meme(message: Message) -> None:
    """Обработчик /мем, /шутка, /анекдот."""
    await _send_random_meme(message)


@router.message(is_meme_request)
async def auto_meme(message: Message) -> None:
    """Если пользователь просит шутку — кидаем случайный мем."""
    await _send_random_meme(message)
