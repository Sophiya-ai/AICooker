"""Сценарий распознавания готового блюда на ранее присланной фотографии."""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from services.recipe_generator import RecipeGenerationError, RecipeGenerator
from services.memory import ConversationMemory
from services.storage import RecipeRepository
from utils.image_tools import telephoto_to_base64
from utils.recipes import publish_recipes

router = Router(name="dish-identify")
LOGGER = logging.getLogger(__name__)


@router.callback_query(F.data == "photo:dish")
async def process_dish_photo(
    callback: CallbackQuery,
    state: FSMContext,
    recipe_generator: RecipeGenerator,
    conversation_memory: ConversationMemory,
    recipe_repository: RecipeRepository,
) -> None:
    """Получить фото из FSM, распознать блюдо и отправить сохранённый рецепт.

    ``callback`` содержит нажатую inline-кнопку и доступ к Bot; ``state`` хранит
    file_id между двумя Telegram-событиями. Остальные аргументы автоматически
    предоставляет DependencyMiddleware из bot.py.
    """

    # Telegram ожидает быстрый ответ на callback. Без answer() кнопка продолжит
    # показывать пользователю индикатор загрузки.
    await callback.answer()

    data = await state.get_data()
    file_id = data.get("file_id")

    if not file_id:
        await callback.message.answer("Не вижу сохранённого фото. Пришли изображение снова.")
        return

    await callback.message.edit_reply_markup()
    chat_id = callback.message.chat.id
    await callback.bot.send_chat_action(chat_id=chat_id, action="typing")
    # Краткая история позволяет модели учитывать предыдущие пожелания в чате.
    history = conversation_memory.format_history(chat_id)

    try:
        # OpenAI принимает изображение как data URI, а Telegram хранит его по id.
        image_data = await telephoto_to_base64(callback.bot, file_id)
        recipes = await recipe_generator.from_dish_photo(
            image_data,
            history or None,
        )
    except RecipeGenerationError:
        LOGGER.exception("Dish photo processing failed")
        await callback.message.answer("⚠️ Не удалось распознать блюдо. Попробуй другое фото.")
        return

    if not recipes:
        await callback.message.answer("⚠️ Модель не смогла описать блюдо. Попробуй новое фото.")
        return

    # Состояние очищается только после успеха: новый снимок сможет начать сценарий заново.
    await state.clear()
    conversation_memory.add(chat_id, "user", "[Фото готового блюда]")
    await publish_recipes(
        callback.message.answer,
        chat_id,
        recipes,
        source="Фото готового блюда",
        recipe_repository=recipe_repository,
        conversation_memory=conversation_memory,
    )

