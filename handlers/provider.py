"""Команда и inline-кнопки выбора платного или бесплатного AI-провайдера."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from services.provider_registry import (
    LOCAL_PROVIDER,
    OPENAI_PROVIDER,
    PROVIDER_TITLES,
    ProviderRegistry,
)

router = Router(name="provider")


def _provider_keyboard(
    registry: ProviderRegistry,
    current: str,
) -> InlineKeyboardMarkup:
    """Создать две кнопки и отметить текущий/недоступный вариант."""

    rows = []
    for provider in (LOCAL_PROVIDER, OPENAI_PROVIDER):
        title = PROVIDER_TITLES[provider]
        if provider == current:
            title = f"✅ {title}"
        elif not registry.is_available(provider):
            title = f"🔒 {title}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=title,
                    callback_data=f"provider:{provider}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _provider_text(current: str) -> str:
    """Пояснить различия вариантов и показать текущий выбор."""

    return (
        "<b>Выбор AI для анализа</b>\n\n"
        f"Сейчас: {PROVIDER_TITLES[current]}\n\n"
        "🆓 <b>Локально</b> — Ollama обрабатывает текст и фото, "
        "faster-whisper распознаёт голос. Оплата и API-ключ не нужны, "
        "но Ollama должна быть запущена на компьютере.\n\n"
        "💳 <b>GPT</b> — OpenAI API. Этот режим станет доступен после "
        "добавления OPENAI_API_KEY в .env и перезапуска бота."
    )


@router.message(Command("provider"))
async def choose_provider(message: Message, provider_registry: ProviderRegistry) -> None:
    """Показать пользователю текущий режим и клавиатуру переключения."""

    current = provider_registry.get_provider(message.chat.id)
    await message.answer(
        _provider_text(current),
        reply_markup=_provider_keyboard(provider_registry, current),
    )


@router.callback_query(F.data.startswith("provider:"))
async def set_provider(
    callback: CallbackQuery,
    provider_registry: ProviderRegistry,
) -> None:
    """Проверить доступность и запомнить выбор для текущего чата."""

    provider = (callback.data or "").split(":", maxsplit=1)[-1]
    chat_id = callback.message.chat.id

    if not provider_registry.select(chat_id, provider):
        if provider == OPENAI_PROVIDER:
            await callback.answer(
                "GPT недоступен: добавьте OPENAI_API_KEY в .env и перезапустите бота.",
                show_alert=True,
            )
        else:
            await callback.answer("Неизвестный AI-провайдер", show_alert=True)
        return

    await callback.message.edit_text(
        _provider_text(provider),
        reply_markup=_provider_keyboard(provider_registry, provider),
    )
    await callback.answer(f"Выбрано: {PROVIDER_TITLES[provider]}")
