"""Короткая оперативная память диалога, существующая только во время запуска."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List


@dataclass(slots=True)
class MemoryRecord:
    """Одна реплика с ролью ``user`` или ``assistant`` и её содержимым."""
    role: str
    content: str


class ConversationMemory:
    """Хранит последние сообщения отдельно для каждого Telegram chat_id.

    Это не база данных: после перезапуска история исчезает. ``deque(maxlen=N)``
    автоматически удаляет самые старые записи и не даёт prompt расти бесконечно.
    """

    def __init__(self, limit: int = 10) -> None:
        """Создать пустое хранилище; ``limit`` задаёт глубину на один чат."""
        self._limit = limit
        self._storage: Dict[int, Deque[MemoryRecord]] = {}

    def add(self, chat_id: int, role: str, content: str) -> None:
        """Добавить очищенную от краевых пробелов реплику в нужный чат."""
        entry = MemoryRecord(role=role, content=content.strip())
        history = self._storage.setdefault(chat_id, deque(maxlen=self._limit))
        history.append(entry)

    def get_history(self, chat_id: int) -> List[MemoryRecord]:
        """Вернуть копию истории, чтобы вызывающий код не менял deque напрямую."""
        return list(self._storage.get(chat_id, []))

    def format_history(self, chat_id: int) -> str:
        """Подготовить историю в текстовом формате для prompt языковой модели."""
        history: Iterable[MemoryRecord] = self._storage.get(chat_id, [])
        return "\n".join(f"{record.role}: {record.content}" for record in history)

    def clear(self, chat_id: int) -> None:
        """Удалить историю одного чата; отсутствие chat_id не считается ошибкой."""
        self._storage.pop(chat_id, None)

