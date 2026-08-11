"""Низкоуровневые операции с голосовыми файлами Telegram."""

from __future__ import annotations

import io

from aiogram import Bot


async def download_voice(bot: Bot, file_id: str) -> bytes:
    """Скачать Telegram-файл по file_id и вернуть его байты из памяти.

    Сначала Telegram API преобразует логический ``file_id`` в ``file_path``,
    после чего Bot скачивает содержимое в BytesIO без временного файла на диске.
    """

    telegram_file = await bot.get_file(file_id)
    buffer = io.BytesIO()
    await bot.download_file(telegram_file.file_path, buffer)
    return buffer.getvalue()

