"""Общий конвейер публикации: БД → кнопка → Telegram → память диалога."""

from __future__ import annotations

from typing import Awaitable, Callable, List

from services.memory import ConversationMemory
from services.recipes.schemas import RecipeData
from services.storage import RecipeRepository
from utils.messages import build_favorite_keyboard, render_recipe

# Handler передаёт bound-метод message.answer. Такой тип показывает, что функция
# принимает произвольные аргументы и возвращает объект, который нужно await.
SendFunc = Callable[..., Awaitable[object]]


async def publish_recipes(
    reply_func: SendFunc,
    chat_id: int,
    recipes: List[RecipeData],
    *,
    source: str,
    recipe_repository: RecipeRepository,
    conversation_memory: ConversationMemory,
) -> None:
    """Сохранить и отправить каждый рецепт, затем обновить краткую историю.

    ``reply_func`` вместо жёсткой зависимости от Message облегчает повторное
    использование для callback-сообщений. Именованные параметры после ``*``
    делают вызов самодокументируемым и защищают от перестановки сервисов.
    """
    titles: list[str] = []
    for recipe in recipes:
        recipe_id = await recipe_repository.add_recipe(
            chat_id,
            recipe,
            source=source,
        )
        markup = build_favorite_keyboard(recipe_id, False)
        await reply_func(render_recipe(recipe), reply_markup=markup)
        titles.append(recipe.title)

    if titles:
        conversation_memory.add(
            chat_id,
            "assistant",
            f"{source}: {', '.join(titles)}",
        )

