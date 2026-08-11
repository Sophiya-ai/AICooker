"""Единый асинхронный адаптер OpenAI для текста, изображений и аудио.

Остальной проект не зависит от деталей SDK и работает с обычными строками и
байтами. Все ошибки SDK преобразуются в доменное исключение OpenAIClientError.
"""

from __future__ import annotations

import io
import logging
from openai import AsyncOpenAI

from services.ai_client import AIClientError

LOGGER = logging.getLogger(__name__)


class OpenAIClientError(AIClientError):
    """Ошибка OpenAI; наследуется от общего типа ошибки AI-провайдера."""


class OpenAIClient:
    """Тонкая асинхронная обёртка над OpenAI Python SDK."""

    def __init__(
        self,
        api_key: str,
        *,
        text_model: str,
        vision_model: str,
        transcribe_model: str,
        temperature: float = 0.6,
    ) -> None:
        """Настроить модели и вариативность ответов.

        Аргументы после ``*`` передаются только по имени. ``temperature=0.6``
        сохраняет разнообразие рецептов, но меньше провоцирует отклонения от JSON,
        чем высокие значения около 1.0.
        """
        self._client = AsyncOpenAI(api_key=api_key)
        self._text_model = text_model
        self._vision_model = vision_model
        self._transcribe_model = transcribe_model
        self._temperature = temperature

    async def generate_text(self, prompt: str) -> str:
        """Отправить один пользовательский prompt выбранной текстовой модели."""

        try:
            response = await self._client.chat.completions.create(
                model=self._text_model,
                temperature=self._temperature,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # pragma: no cover - network failure
            raise OpenAIClientError("Не удалось получить ответ от OpenAI") from exc

        # API допускает content=None; нижние слои проекта всегда ожидают строку.
        content = response.choices[0].message.content or ""
        LOGGER.debug("Text completion tokens: %s", response.usage)
        return content.strip()

    async def generate_vision(
        self,
        prompt: str,
        image_base64_url: str,
    ) -> str:
        """Передать модели совместное сообщение из инструкции и data URI фото."""

        # Мультимодальное content — список частей; их порядок сообщает модели,
        # какую инструкцию применить к следующему изображению.
        payload = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_base64_url}},
        ]

        try:
            response = await self._client.chat.completions.create(
                model=self._vision_model,
                temperature=self._temperature,
                messages=[{"role": "user", "content": payload}],
            )
        except Exception as exc:  # pragma: no cover - network failure
            raise OpenAIClientError("OpenAI Vision запрос завершился ошибкой") from exc

        content = response.choices[0].message.content or ""
        LOGGER.debug("Vision completion tokens: %s", response.usage)
        return content.strip()

    async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
        """Распознать короткое аудио, например голосовое сообщение Telegram."""

        # BytesIO позволяет не создавать временный файл на диске. Атрибут name
        # нужен SDK для определения расширения/формата контейнера.
        buffer = io.BytesIO(audio_bytes)
        buffer.name = filename

        try:
            response = await self._client.audio.transcriptions.create(
                model=self._transcribe_model,
                file=buffer,
                response_format="text",
            )
        except Exception as exc:  # pragma: no cover - network failure
            raise OpenAIClientError("Не удалось распознать голосовое сообщение") from exc

        transcript = getattr(response, "text", "") or ""
        LOGGER.debug("Transcription result length: %s chars", len(transcript))
        return transcript.strip()


