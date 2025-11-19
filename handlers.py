# -*- coding: utf-8 -*-
"""
Модуль для обработки входящих сообщений и команд от пользователя в Telegram.
"""
import logging
import os
import asyncio
from functools import partial

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    ContentType,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.markdown import hbold

from services import report_validator, message_rewriter, parse_docx, parse_pdf

# Создаем роутер для обработчиков
router = Router()

# ---- Вспомогательные функции ----
def create_rewrite_keyboard(variant1_text: str, variant2_text: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками для выбора варианта рерайта."""
    button1 = InlineKeyboardButton(text="Выбрать Вариант 1", callback_data="rewrite_option_1")
    button2 = InlineKeyboardButton(text="Выбрать Вариант 2", callback_data="rewrite_option_2")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button1], [button2]])
    return keyboard

# ---- Обработчики команд и сообщений ----
@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    Обработчик команды /start. Приветствует пользователя.
    """
    await message.answer(
        f"Здравствуйте, {hbold(message.from_user.full_name)}!\n\n"
        "Я ваш ассистент 'Cortex'. Моя задача — помочь вам подготовить контент для отправки руководству.\n\n"
        "Вы можете:\n"
        "• Отправить мне текстовое сообщение, и я предложу улучшенные варианты.\n"
        "• Загрузить отчет в формате .docx или .pdf, и я проведу его первичную оценку."
    )

@router.message(F.document)
async def document_handler(message: Message, bot: Bot) -> None:
    """
    Обработчик входящих документов. Проверяет отчеты.
    """
    if not message.document:
        return

    file = message.document
    file_name = file.file_name or "unknown"

    if not (file_name.lower().endswith(".docx") or file_name.lower().endswith(".pdf")):
        await message.reply("Пожалуйста, отправьте файл в формате .docx или .pdf.")
        return

    await message.reply("Анализирую ваш отчет... Это может занять некоторое время.")

    try:
        # Скачиваем файл
        file_info = await bot.get_file(file.file_id)
        if not file_info.file_path:
            raise ValueError("Не удалось получить путь к файлу.")

        file_content = await bot.download_file(file_info.file_path)
        if not file_content:
            raise ValueError("Не удалось скачать файл.")

        # Парсим в зависимости от типа
        loop = asyncio.get_running_loop()
        text = ""
        if file_name.lower().endswith(".pdf"):
            # Запускаем синхронную функцию в отдельном потоке
            text = await loop.run_in_executor(None, partial(parse_pdf, file_content.read()))
        elif file_name.lower().endswith(".docx"):
            text = await loop.run_in_executor(None, partial(parse_docx, file_content.read()))

        # Валидируем
        validation_result = await report_validator.validate(text)
        await message.reply(validation_result)

    except (ValueError, TypeError) as e:
        logging.error(f"Ошибка обработки файла {file_name}: {e}")
        await message.reply(f"Произошла ошибка при обработке файла: {e}")
    except Exception as e:
        logging.error(f"Критическая ошибка при обработке файла {file_name}: {e}")
        await message.reply("Произошла непредвиденная ошибка. Попробуйте еще раз позже.")


@router.message(F.text)
async def text_message_handler(message: Message) -> None:
    """
    Обработчик текстовых сообщений. Предлагает рерайтинг.
    """
    if not message.text:
        return

    await message.reply("Анализирую ваше сообщение и готовлю варианты...")

    rewrite_result = await message_rewriter.rewrite(message.text)

    if rewrite_result is None:
        await message.reply("К сожалению, не удалось обработать ваше сообщение. Попробуйте переформулировать его.")
        return

    response_text = (
        f"{hbold('Что исправлено:')}\n{rewrite_result['critique']}\n\n"
        f"{hbold('Вариант 1 (Строго-официальный):')}\n{rewrite_result['variant1']}\n\n"
        f"{hbold('Вариант 2 (Лаконично-деловой):')}\n{rewrite_result['variant2']}"
    )

    keyboard = create_rewrite_keyboard(rewrite_result['variant1'], rewrite_result['variant2'])

    await message.answer(response_text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("rewrite_option_"))
async def rewrite_callback_handler(callback_query: CallbackQuery):
    """
    Обработчик нажатий на inline-кнопки выбора варианта рерайта.
    """
    await callback_query.answer() # Снимаем "часики" с кнопки

    # Получаем номер выбранного варианта
    option_number = callback_query.data.split("_")[-1]

    logging.info(
        f"Пользователь {callback_query.from_user.id} выбрал вариант рерайта #{option_number}"
    )

    # Редактируем исходное сообщение, убирая клавиатуру
    await callback_query.message.edit_reply_markup(reply_markup=None)

    # Отправляем подтверждение
    await callback_query.message.answer(
        f"Отлично! Вы выбрали вариант {option_number}. Этот выбор будет учтен в будущем."
    )

def register_handlers(dp: Dispatcher):
    """
    Регистрирует все обработчики в главном диспетчере.
    """
    dp.include_router(router)
