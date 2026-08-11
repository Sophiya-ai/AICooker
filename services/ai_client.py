"""Общий контракт для платного и бесплатного AI-провайдеров.

RecipeGenerator и Telegram-handler'ы работают с этим интерфейсом и не знают,
отправлен запрос в OpenAI или в локальные Ollama/faster-whisper. Благодаря этому
провайдера можно менять без копирования бизнес-логики.
"""

from __future__ import annotations

from typing import Protocol


class AIClientError(RuntimeError):
    """Единая ошибка любого AI-провайдера, безопасная для обработки в handler."""


class AIClient(Protocol):
    """Минимальный набор операций, необходимых кулинарному ассистенту."""

    async def generate_text(self, prompt: str) -> str:
        """Сгенерировать текстовый ответ по prompt."""

        ...

    async def generate_vision(self, prompt: str, image_base64_url: str) -> str:
        """Проанализировать изображение и вернуть текстовый ответ."""

        ...

    async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
        """Преобразовать записанное аудио в текст."""

        ...
