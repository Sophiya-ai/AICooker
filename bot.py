"""Точка входа AI Cooking Assistant.

Здесь создаются общие сервисы, подключаются обработчики Telegram, запускаются
long polling и HTTP-сервер Mini App. Модуль не содержит рецептурной логики: его
задача — связать отдельные части приложения (composition root).
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from aiohttp import web
from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import get_settings
from handlers import (
    dish_identify,
    favorites,
    image_ingredients,
    interactive_flow,
    provider,
    start,
    text_recipe,
    voice_recipe,
    webapp_data,
)
from services.interactive_chef import InteractiveChef
from services.local_ai_client import LocalAIClient
from services.memory import ConversationMemory
from services.ngrok_tunnel import NgrokTunnel
from services.openai_client import OpenAIClient
from services.provider_registry import ProviderRegistry
from services.recipe_generator import RecipeGenerator
from services.storage import RecipeRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger("bot")


class DependencyMiddleware(BaseMiddleware):
    """Передаёт созданные сервисы в аргументы каждого обработчика aiogram.

    Такой механизм называется внедрением зависимостей. Например, параметр
    ``recipe_generator`` в handler-функции будет взят из ``self._dependencies``.
    Тяжёлые клиенты создаются один раз. Лёгкие RecipeGenerator/InteractiveChef
    создаются для события с клиентом, выбранным именно в этом Telegram-чате.
    """

    def __init__(self, provider_registry: ProviderRegistry, **dependencies) -> None:
        """Сохранить registry AI-провайдеров и остальные общие зависимости."""
        super().__init__()
        self._provider_registry = provider_registry
        self._dependencies = dependencies

    async def __call__(self, handler, event, data):
        """Добавить зависимости в контекст события и продолжить цепочку."""
        data.update(self._dependencies)
        data["provider_registry"] = self._provider_registry

        # У Message chat находится прямо в event.chat, у CallbackQuery — внутри
        # event.message.chat. Middleware поддерживает оба типа событий.
        chat = getattr(event, "chat", None)
        if chat is None:
            event_message = getattr(event, "message", None)
            chat = getattr(event_message, "chat", None)

        if chat is not None:
            ai_client = self._provider_registry.get_client(chat.id)
            data["ai_client"] = ai_client
            data["recipe_generator"] = RecipeGenerator(ai_client)
            data["interactive_chef"] = InteractiveChef(ai_client, max_questions=3)
        return await handler(event, data)


async def set_commands(bot: Bot) -> None:
    """Зарегистрировать команды, которые Telegram показывает в меню бота."""
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="help", description="Как работает ассистент"),
        BotCommand(command="provider", description="Выбрать GPT или бесплатный AI"),
        BotCommand(command="chef", description="Интерактивный сбор требований"),
        BotCommand(command="miniapp", description="Открыть мини-приложение"),
    ]
    await bot.set_my_commands(commands)


async def start_miniapp_server(
    directory: Path,
    host: str,
    port: int,
) -> Optional[web.AppRunner]:
    """Запустить простой сервер статических файлов Mini App.

    ``directory`` — папка HTML/CSS/JS; ``host`` определяет сетевой интерфейс,
    ``port`` — TCP-порт. Возвращается runner для корректной остановки сервера.
    Если папки нет, Mini App отключается, но сам Telegram-бот продолжает работу.
    """
    if not directory.exists():
        LOGGER.warning("Miniapp directory %s не найден, сервер не запущен", directory)
        return None

    app = web.Application()

    async def index(_: web.Request):
        """Отдать главную HTML-страницу; объект запроса здесь не используется."""
        return web.FileResponse(directory / "index.html")

    app.router.add_get("/", index)
    app.router.add_static("/static/", path=directory, name="miniapp-static")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    LOGGER.info("Miniapp доступен по адресу http://%s:%s", host, port)
    return runner


async def main() -> None:
    """Собрать приложение, инициализировать ресурсы и начать polling."""

    # Настройки загружаются до создания внешних клиентов: при неверном .env бот
    # завершится сразу, а не при первом пользовательском сообщении.
    settings = get_settings()
    bot = Bot(
        token=settings.telegram_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Бесплатный клиент регистрируется всегда. Модели не загружаются на старте:
    # Ollama вызывается по HTTP, Whisper лениво создаётся при первом voice.
    local_client = LocalAIClient(
        ollama_host=settings.ollama_host,
        text_model=settings.ollama_text_model,
        vision_model=settings.ollama_vision_model,
        whisper_model=settings.whisper_model,
        whisper_device=settings.whisper_device,
        whisper_compute_type=settings.whisper_compute_type,
    )

    clients = {"local": local_client}
    # OpenAI-клиент создаётся только при наличии ключа. Поэтому отсутствие оплаты
    # и пустой OPENAI_API_KEY больше не мешают запуску бесплатного режима.
    if settings.openai_api_key:
        clients["openai"] = OpenAIClient(
            api_key=settings.openai_api_key,
            text_model=settings.openai_text_model,
            vision_model=settings.openai_vision_model,
            transcribe_model=settings.openai_transcribe_model,
        )

    provider_registry = ProviderRegistry(
        clients,
        default_provider=settings.default_ai_provider,
    )
    conversation_memory = ConversationMemory(limit=12)
    recipe_repository = RecipeRepository(settings.database_path)
    await recipe_repository.init()

    # MemoryStorage хранит FSM-состояния в RAM. Это удобно для MVP, но состояния
    # активных диалогов пропадут при перезапуске; для production лучше Redis.
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dependency_middleware = DependencyMiddleware(
        provider_registry,
        conversation_memory=conversation_memory,
        recipe_repository=recipe_repository,
    )

    # Порядок важен: специализированные сценарии подключаются до общих, а у
    # текстового handler дополнительно есть фильтр default_state.
    for router in (
        start.router,
        provider.router,
        text_recipe.router,
        voice_recipe.router,
        image_ingredients.router,
        dish_identify.router,
        interactive_flow.router,
        webapp_data.router,
        favorites.router,
    ):
        router.message.middleware(dependency_middleware)
        router.callback_query.middleware(dependency_middleware)
        dp.include_router(router)

    web_runner: Optional[web.AppRunner] = None
    ngrok_tunnel: Optional[NgrokTunnel] = None
    # finally освобождает HTTP-ресурсы даже после Ctrl+C или ошибки polling.
    try:
        # Telegram-бот и сервер Mini App живут в одном asyncio-процессе. Это
        # одинаково работает локально и на сервере; отличается только источник
        # публичного HTTPS URL.
        web_runner = await start_miniapp_server(
            settings.miniapp_path,
            settings.webapp_host,
            settings.webapp_port,
        )

        if settings.enable_ngrok:
            # Локальный режим: pyngrok публикует тот же aiohttp-порт и возвращает
            # временный HTTPS URL. Handlers читают обновлённое значение Settings.
            ngrok_tunnel = NgrokTunnel(
                port=settings.webapp_port,
                authtoken=settings.ngrok_authtoken,
            )
            settings.webapp_url = await ngrok_tunnel.start()

        await set_commands(bot)
        LOGGER.info("Bot started. Waiting for updates...")
        await dp.start_polling(bot)
    finally:
        if ngrok_tunnel:
            LOGGER.info("Останавливаем ngrok туннель...")
            await ngrok_tunnel.stop()
        if web_runner:
            LOGGER.info("Останавливаем miniapp сервер...")
            await web_runner.cleanup()


if __name__ == "__main__":
    # Условие не запускает бота при обычном import (например, в тестах).
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        LOGGER.info("Bot stopped.")

