"""Подготовка Telegram-фотографии к мультимодальному запросу OpenAI."""

from __future__ import annotations

import base64
import io

from aiogram import Bot
from PIL import Image


async def telephoto_to_base64(bot: Bot, file_id: str) -> str:
    """Скачать фото, нормализовать в JPEG и вернуть data URI.

    ``RGB`` устраняет проблемы с прозрачностью и нестандартными цветовыми
    режимами. Quality 90 даёт хороший компромисс между детализацией и размером.
    Data URI имеет вид ``data:image/jpeg;base64,...`` и принимается vision API.
    """

    telegram_file = await bot.get_file(file_id)
    buffer = io.BytesIO()
    await bot.download_file(telegram_file.file_path, buffer)
    buffer.seek(0)

    # seek(0) возвращает указатель в начало после записи скачанных байтов.
    image = Image.open(buffer)
    processed = io.BytesIO()
    image.convert("RGB").save(processed, format="JPEG", quality=90)
    processed.seek(0)

    encoded = base64.b64encode(processed.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"

