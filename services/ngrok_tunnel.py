"""Опциональный HTTPS-туннель ngrok для локального запуска Mini App.

Telegram принимает для Web App только HTTPS URL, тогда как встроенный aiohttp-
сервер слушает обычный локальный HTTP. Ngrok выдаёт временный публичный HTTPS-
адрес и перенаправляет запросы на локальный порт. На production-сервере этот
модуль не используется: там HTTPS обычно завершает reverse proxy.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from pyngrok import ngrok
from pyngrok.exception import PyngrokError

LOGGER = logging.getLogger(__name__)


class NgrokTunnel:
    """Управляет жизненным циклом одного туннеля, принадлежащего приложению."""

    def __init__(self, *, port: int, authtoken: str) -> None:
        """Запомнить локальный порт и секретный токен аккаунта ngrok.

        Параметры сделаны именованными через ``*``, чтобы при создании объекта
        нельзя было случайно поменять местами целое число и строку-секрет.
        """

        self._port = port
        self._authtoken = authtoken
        self._public_url: Optional[str] = None

    @property
    def public_url(self) -> Optional[str]:
        """Вернуть URL активного туннеля или None до его запуска."""

        return self._public_url

    async def start(self) -> str:
        """Запустить ngrok в рабочем потоке и вернуть публичный HTTPS URL.

        Pyngrok выполняет блокирующие операции и при первом старте может скачать
        ngrok agent. ``asyncio.to_thread`` не блокирует event loop Telegram-бота.
        """

        try:
            public_url = await asyncio.to_thread(self._start_sync)
        except PyngrokError as exc:
            raise RuntimeError(
                "Не удалось запустить ngrok. Проверьте NGROK_AUTHTOKEN, "
                "подключение к интернету и отсутствие другого ngrok-процесса."
            ) from exc

        if not public_url.startswith("https://"):
            # WebAppInfo в Telegram требует именно HTTPS, поэтому HTTP endpoint
            # нельзя молча принять как корректный результат.
            await self.stop()
            raise RuntimeError(f"ngrok вернул не-HTTPS адрес: {public_url}")

        self._public_url = public_url.rstrip("/")
        LOGGER.info("Публичный адрес Mini App: %s", self._public_url)
        return self._public_url

    def _start_sync(self) -> str:
        """Синхронная часть, которую ``start`` запускает вне event loop."""

        # set_auth_token сохраняет токен в конфигурации ngrok agent. Сам токен
        # никогда не выводится в журнал.
        ngrok.set_auth_token(self._authtoken)
        tunnel = ngrok.connect(str(self._port), "http")
        return tunnel.public_url

    async def stop(self) -> None:
        """Закрыть endpoint и фоновый ngrok agent при остановке приложения."""

        if self._public_url:
            await asyncio.to_thread(ngrok.disconnect, self._public_url)
            self._public_url = None

        # kill завершает только agent-процесс, которым управляет pyngrok в этом
        # Python-приложении; без этого он мог бы остаться после Ctrl+C.
        await asyncio.to_thread(ngrok.kill)
