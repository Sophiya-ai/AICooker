"""Доступные AI-провайдеры и выбор провайдера отдельно для каждого чата."""

from __future__ import annotations

from typing import Dict, Mapping

from services.ai_client import AIClient

LOCAL_PROVIDER = "local"
OPENAI_PROVIDER = "openai"
PROVIDER_TITLES = {
    LOCAL_PROVIDER: "🆓 Локально (Ollama + Whisper)",
    OPENAI_PROVIDER: "💳 GPT (OpenAI API)",
}


class ProviderRegistry:
    """Хранит клиентов и пользовательский выбор в оперативной памяти."""

    def __init__(
        self,
        clients: Mapping[str, AIClient],
        *,
        default_provider: str = LOCAL_PROVIDER,
    ) -> None:
        """Проверить default и скопировать доступных клиентов.

        OpenAI отсутствует в ``clients``, если ключ не задан. Локальный клиент
        создаётся всегда, но фактическая доступность Ollama проверяется при запросе.
        """

        self._clients = dict(clients)
        if default_provider not in self._clients:
            default_provider = LOCAL_PROVIDER
        if default_provider not in self._clients:
            raise ValueError("Не зарегистрирован ни один AI-провайдер")
        self._default_provider = default_provider
        self._selection: Dict[int, str] = {}

    def get_provider(self, chat_id: int) -> str:
        """Вернуть выбор чата или бесплатный/default режим для нового чата."""

        return self._selection.get(chat_id, self._default_provider)

    def get_client(self, chat_id: int) -> AIClient:
        """Вернуть клиент, соответствующий текущему выбору чата."""

        return self._clients[self.get_provider(chat_id)]

    def is_available(self, provider: str) -> bool:
        """Проверить, сконфигурирован ли провайдер в этом процессе."""

        return provider in self._clients

    def select(self, chat_id: int, provider: str) -> bool:
        """Сохранить доступный provider; вернуть False для неизвестного/недоступного."""

        if not self.is_available(provider):
            return False
        self._selection[chat_id] = provider
        return True
