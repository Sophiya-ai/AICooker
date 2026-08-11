"""Загрузка настроек приложения из файла ``.env`` и переменных окружения.

Этот модуль отделяет конфигурацию от бизнес-логики: токены и адреса не
записываются прямо в код, поэтому один и тот же проект можно безопасно запускать
на разных компьютерах. Обязательные секреты проверяются при старте бота.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Абсолютный путь к папке проекта. Он служит надёжной точкой отсчёта для БД и
# статических файлов независимо от того, из какой папки выполнена команда python.
BASE_DIR = Path(__file__).resolve().parent


@dataclass(slots=True)
class Settings:
    """Типизированный контейнер всех настроек приложения.

    ``slots=True`` запрещает случайно создавать новые атрибуты с опечатками и
    немного уменьшает расход памяти. Типы полей помогают IDE подсвечивать ошибки.
    """

    telegram_token: str
    openai_api_key: str
    openai_text_model: str
    openai_vision_model: str
    openai_transcribe_model: str
    webapp_host: str
    webapp_port: int
    webapp_url: str
    enable_ngrok: bool
    ngrok_authtoken: str
    miniapp_path: Path
    database_path: Path


def _load_from_env() -> Settings:
    """Прочитать окружение, проверить обязательные значения и собрать Settings."""

    # load_dotenv ищет .env и переносит пары ИМЯ=значение в os.environ.
    # Уже заданные системные переменные по умолчанию имеют приоритет.
    load_dotenv()

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_text_model = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
    openai_vision_model = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
    openai_transcribe_model = os.getenv(
        "OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"
    )
    webapp_host = os.getenv("WEBAPP_HOST", "127.0.0.1")
    # os.getenv всегда возвращает строку, тогда как aiohttp ожидает номер порта
    # как int. Некорректное значение намеренно приводит к понятной ошибке старта.
    webapp_port = int(os.getenv("WEBAPP_PORT", "8080"))
    webapp_url = os.getenv("WEBAPP_URL", "")
    # ENABLE_NGROK — переключатель локального режима «всё одной командой».
    # Приводим значение к lowercase и принимаем несколько привычных вариантов.
    enable_ngrok = os.getenv("ENABLE_NGROK", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    ngrok_authtoken = os.getenv("NGROK_AUTHTOKEN", "").strip()
    miniapp_path = Path(os.getenv("WEBAPP_STATIC_DIR", BASE_DIR / "miniapp")).resolve()
    database_path = Path(os.getenv("DATABASE_PATH", BASE_DIR / "recipes.db")).resolve()

    # Имена отсутствующих секретов собираются вместе, чтобы пользователь мог
    # исправить .env за один раз, а не запускать проект после каждой правки.
    missing = [
        name
        for name, value in (
            ("TELEGRAM_BOT_TOKEN", telegram_token),
            ("OPENAI_API_KEY", openai_api_key),
        )
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Отсутствуют обязательные переменные окружения: "
            + ", ".join(missing)
        )

    if enable_ngrok and not ngrok_authtoken:
        raise RuntimeError(
            "ENABLE_NGROK=true, но NGROK_AUTHTOKEN не задан. "
            "Добавьте токен ngrok в .env или выключите автоматический туннель."
        )

    return Settings(
        telegram_token=telegram_token,
        openai_api_key=openai_api_key,
        openai_text_model=openai_text_model,
        openai_vision_model=openai_vision_model,
        openai_transcribe_model=openai_transcribe_model,
        webapp_host=webapp_host,
        webapp_port=webapp_port,
        webapp_url=webapp_url,
        enable_ngrok=enable_ngrok,
        ngrok_authtoken=ngrok_authtoken,
        miniapp_path=miniapp_path,
        database_path=database_path,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Вернуть настройки, загрузив их только при первом вызове.

    ``lru_cache(maxsize=1)`` гарантирует единый объект настроек на всё приложение
    и исключает повторное чтение .env в каждом обработчике.
    """

    return _load_from_env()

