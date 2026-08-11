"""Асинхронное SQLite-хранилище рецептов и признака «избранное»."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import aiosqlite

from services.recipes.schemas import RecipeData

# JSON-массивы сохраняются в TEXT-полях: для небольшого MVP это проще, чем
# создавать отдельные связанные таблицы ингредиентов, шагов и вариаций.
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    cook_time TEXT,
    ingredients TEXT NOT NULL,
    steps TEXT NOT NULL,
    missing_items TEXT,
    variations TEXT,
    serving_tips TEXT,
    source TEXT,
    is_favorite INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@dataclass(slots=True)
class RecipeRecord:
    """Краткое представление записи (оставлено для будущей выдачи избранного)."""
    id: int
    title: str
    is_favorite: bool


class RecipeRepository:
    """Изолирует SQL от обработчиков и сервисов генерации."""

    def __init__(self, database_path: Path) -> None:
        """Запомнить путь; соединение открывается отдельно на каждую операцию."""
        self._path = database_path

    async def init(self) -> None:
        """Создать родительскую папку и таблицу, если их ещё нет."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._path) as db:
            await db.execute(CREATE_TABLE_SQL)
            await db.commit()

    async def add_recipe(
        self,
        chat_id: int,
        recipe: RecipeData,
        *,
        source: str,
    ) -> int:
        """Сохранить рецепт и вернуть созданный SQLite primary key.

        ``source`` сделан keyword-only, чтобы при вызове было явно видно,
        каким сценарием создан рецепт. Знаки ``?`` обеспечивают безопасную
        параметризацию SQL вместо склеивания пользовательских строк.
        """
        async with aiosqlite.connect(self._path) as db:
            cursor = await db.execute(
                """
                INSERT INTO recipes (
                    chat_id,
                    title,
                    cook_time,
                    ingredients,
                    steps,
                    missing_items,
                    variations,
                    serving_tips,
                    source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    recipe.title,
                    recipe.cook_time,
                    self._dump(recipe.ingredients),
                    self._dump(recipe.steps),
                    self._dump(recipe.missing_items),
                    self._dump(recipe.variations),
                    self._dump(recipe.serving_tips),
                    source,
                ),
            )
            await db.commit()
            return cursor.lastrowid

    async def toggle_favorite(self, recipe_id: int) -> Optional[bool]:
        """Инвертировать флаг и вернуть новое состояние либо None без записи."""
        async with aiosqlite.connect(self._path) as db:
            cursor = await db.execute(
                "SELECT is_favorite FROM recipes WHERE id = ?", (recipe_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None

            current = row[0] == 1
            new_value = 0 if current else 1
            await db.execute(
                "UPDATE recipes SET is_favorite = ? WHERE id = ?",
                (new_value, recipe_id),
            )
            await db.commit()
            return bool(new_value)

    @staticmethod
    def _dump(items: Iterable[str] | None) -> str:
        """Сериализовать список в читаемый Unicode JSON; None становится []."""
        return json.dumps(list(items or []), ensure_ascii=False)

