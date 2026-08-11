"""Бесплатный локальный AI: Ollama для текста/фото и faster-whisper для голоса.

Модели выполняются на компьютере пользователя и не требуют API-ключа или оплаты.
Ollama должен быть установлен и запущен отдельно как локальная служба. Whisper-
модель загружается лениво при первом голосовом сообщении, а не при старте бота.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

import aiohttp
from faster_whisper import WhisperModel

from services.ai_client import AIClientError

LOGGER = logging.getLogger(__name__)


class LocalAIClient:
    """Реализует общий AI-интерфейс с помощью локальных open-source моделей."""

    def __init__(
        self,
        *,
        ollama_host: str,
        text_model: str,
        vision_model: str,
        whisper_model: str,
        whisper_device: str,
        whisper_compute_type: str,
        temperature: float = 0.2,
        timeout_seconds: int = 300,
    ) -> None:
        """Сохранить адреса и параметры моделей без их немедленной загрузки.

        Низкая ``temperature=0.2`` помогает небольшой локальной модели соблюдать
        JSON. Большой timeout нужен потому, что CPU-генерация может быть медленной.
        Аргументы именованные, чтобы конфигурацию было трудно перепутать.
        """

        self._ollama_host = ollama_host.rstrip("/")
        self._text_model = text_model
        self._vision_model = vision_model
        self._whisper_model_name = whisper_model
        self._whisper_device = whisper_device
        self._whisper_compute_type = whisper_compute_type
        self._temperature = temperature
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._whisper: Optional[WhisperModel] = None
        self._whisper_lock = asyncio.Lock()

    async def generate_text(self, prompt: str) -> str:
        """Отправить текст в локальный `/api/chat` Ollama без streaming."""

        payload = {
            "model": self._text_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": self._temperature},
        }
        return await self._ollama_chat(payload)

    async def generate_vision(self, prompt: str, image_base64_url: str) -> str:
        """Передать prompt и чистый base64 vision-модели Ollama.

        OpenAI принимает полный data URI, а Ollama REST API ожидает содержимое
        после запятой. Поэтому служебный префикс удаляется только в этом адаптере.
        """

        image_base64 = image_base64_url.split(",", maxsplit=1)[-1]
        payload = {
            "model": self._vision_model,
            "messages": [
                {"role": "user", "content": prompt, "images": [image_base64]}
            ],
            "stream": False,
            "options": {"temperature": self._temperature},
        }
        return await self._ollama_chat(payload)

    async def _ollama_chat(self, payload: dict[str, Any]) -> str:
        """Выполнить HTTP-запрос и извлечь `message.content` из ответа Ollama."""

        url = f"{self._ollama_host}/api/chat"
        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status >= 400:
                        details = (await response.text())[:500]
                        raise AIClientError(
                            f"Ollama вернула HTTP {response.status}: {details}"
                        )
                    data = await response.json()
        except AIClientError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise AIClientError(
                "Не удалось подключиться к Ollama. Убедитесь, что Ollama запущена "
                f"по адресу {self._ollama_host}."
            ) from exc

        content = data.get("message", {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise AIClientError("Ollama вернула пустой или некорректный ответ")
        return content.strip()

    async def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
        """Распознать Telegram OGG локальной моделью faster-whisper.

        Faster-whisper выполняет тяжёлые синхронные вычисления, поэтому они
        переносятся в рабочий поток. Временный файл нужен библиотеке/FFmpeg для
        надёжного определения контейнера по расширению и удаляется в ``finally``.
        """

        suffix = Path(filename).suffix or ".ogg"
        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = Path(temp_file.name)

            model = await self._get_whisper_model()
            return await asyncio.to_thread(self._transcribe_sync, model, temp_path)
        except AIClientError:
            raise
        except Exception as exc:
            raise AIClientError("Локальное распознавание голоса завершилось ошибкой") from exc
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)

    async def _get_whisper_model(self) -> WhisperModel:
        """Один раз лениво загрузить Whisper, защищаясь от параллельных вызовов."""

        if self._whisper is not None:
            return self._whisper

        async with self._whisper_lock:
            if self._whisper is None:
                LOGGER.info("Загружаем локальную Whisper-модель %s...", self._whisper_model_name)
                self._whisper = await asyncio.to_thread(
                    WhisperModel,
                    self._whisper_model_name,
                    device=self._whisper_device,
                    compute_type=self._whisper_compute_type,
                )
        return self._whisper

    @staticmethod
    def _transcribe_sync(model: WhisperModel, audio_path: Path) -> str:
        """Полностью вычислить ленивый генератор сегментов Whisper."""

        segments, _ = model.transcribe(
            str(audio_path),
            language="ru",
            vad_filter=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
