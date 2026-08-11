"""Prompt-шаблоны и преобразование ответов модели в объекты RecipeData."""

from __future__ import annotations

from typing import List

from services.recipes.schemas import RecipeData, parse_recipes_payload

from .openai_client import OpenAIClient, OpenAIClientError

# Этот общий контракт повторно используется для всех типов входа. Удвоенные
# скобки экранируют JSON при последующем вызове str.format.
JSON_INSTRUCTION = """
Ответ строго в формате JSON без пояснений:
{
  "recipes": [
    {
      "title": "Название блюда",
      "cook_time": "30 минут",
      "ingredients": ["ингредиент 1", "ингредиент 2"],
      "steps": ["Шаг 1", "Шаг 2"],
      "missing_items": ["что нужно докупить"],
      "variations": ["вариант 1"],
      "serving_tips": ["совет по подаче"]
    }
  ]
}
""".strip().replace("{", "{{").replace("}", "}}")


TEXT_PROMPT = """
Ты — профессиональный шеф-повар.
Пользователь ввёл список продуктов.
Твоя задача:
- предложить 3 блюда;
- перечислить ингредиенты;
- указать время приготовления;
- расписать 5–7 шагов;
- перечислить недостающие продукты, возможные вариации и советы по подаче.
Массив `recipes` должен содержать ровно 3 объекта.

Список пользователя:
{user_input}

{json_instruction}
""".strip()


INGREDIENT_PHOTO_PROMPT = """
Ты — компьютерное зрение + эксперт-повар.
Пользователь прислал фото ингредиентов.
1. Определи продукты на фото.
2. Перечисли их.
3. Предложи 3 блюда (массив `recipes` из 3 объектов).
4. Для каждого блюда дай время, 5–7 шагов, вариации и советы по подаче.
5. Отдельно перечисли, чего может не хватать.

{json_instruction}
""".strip()


DISH_PHOTO_PROMPT = """
Пользователь прислал фото готового блюда.
Твоя задача:
- определить блюдо;
- перечислить ингредиенты;
- дать 5–7 шагов приготовления и примерное время;
- описать 3 вариации;
- дать советы по подаче.
Верни 1 основной рецепт (массив `recipes` содержит один объект).

{json_instruction}
""".strip()


class RecipeGenerationError(RuntimeError):
    """Скрывает от handler-слоя различие между сетевой и JSON-ошибкой."""


class RecipeGenerator:
    """Инкапсулирует prompt engineering для трёх сценариев рецепта."""

    def __init__(self, client: OpenAIClient) -> None:
        """Получить уже настроенный API-клиент через внедрение зависимости."""
        self._client = client

    async def from_text(self, user_text: str, history: str | None = None) -> List[RecipeData]:
        """Сгенерировать три рецепта из текста и необязательной истории чата."""
        prompt = TEXT_PROMPT.format(
            user_input=user_text.strip(),
            json_instruction=JSON_INSTRUCTION,
        )
        prompt = self._with_history(prompt, history)
        raw = await self._call(self._client.generate_text, prompt)
        return self._parse(raw)

    async def from_ingredient_photo(
        self,
        image_base64_url: str,
        history: str | None = None,
    ) -> List[RecipeData]:
        """Распознать продукты на изображении и вернуть три рецепта."""
        prompt = self._with_history(
            INGREDIENT_PHOTO_PROMPT.format(json_instruction=JSON_INSTRUCTION),
            history,
        )
        raw = await self._call(
            self._client.generate_vision,
            prompt,
            image_base64_url,
        )
        return self._parse(raw)

    async def from_dish_photo(
        self,
        image_base64_url: str,
        history: str | None = None,
    ) -> List[RecipeData]:
        """Определить готовое блюдо на изображении и восстановить один рецепт."""
        prompt = self._with_history(
            DISH_PHOTO_PROMPT.format(json_instruction=JSON_INSTRUCTION),
            history,
        )
        raw = await self._call(
            self._client.generate_vision,
            prompt,
            image_base64_url,
        )
        return self._parse(raw)

    @staticmethod
    def _with_history(prompt: str, history: str | None) -> str:
        """Добавить контекст только тогда, когда он действительно существует."""
        if history:
            return f"История диалога:\n{history}\n\n{prompt}"
        return prompt

    async def _call(self, func, *args, **kwargs) -> str:
        """Вызвать text/vision-функцию и унифицировать исключения слоя API."""
        try:
            return await func(*args, **kwargs)
        except OpenAIClientError as exc:  # pragma: no cover - network failure
            raise RecipeGenerationError(str(exc)) from exc

    def _parse(self, raw: str) -> List[RecipeData]:
        """Проверить JSON и унифицировать исключения слоя разбора."""
        try:
            return parse_recipes_payload(raw)
        except ValueError as exc:
            raise RecipeGenerationError(str(exc)) from exc

