# -*- coding: utf-8 -*-
"""
Модуль для обработки входящих сообщений и команд от пользователя в Telegram.
"""
import logging
import os
import asyncio
import uuid
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

    # Защита от OOM: проверяем размер файла (лимит 20 МБ)
    file_size = file.file_size or 0
    if file_size > 20 * 1024 * 1024:
        await message.reply("Файл слишком большой. Максимальный размер — 20 МБ.")
        return

    if not (file_name.lower().endswith(".docx") or file_name.lower().endswith(".pdf")):
        await message.reply("Пожалуйста, отправьте файл в формате .docx или .pdf.")
        return

    await message.reply("Анализирую ваш отчет... Это может занять некоторое время.")

    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    # Генерируем уникальное имя файла, чтобы избежать конфликтов
    tmp_file_path = os.path.join(tmp_dir, f"{uuid.uuid4()}_{file_name}")

    try:
        # Скачиваем файл напрямую на диск
        await bot.download(file=file.file_id, destination=tmp_file_path)
        logging.info(f"Файл '{file_name}' временно сохранен в '{tmp_file_path}'.")

        # Читаем файл с диска для парсинга
        with open(tmp_file_path, "rb") as f:
            file_content_bytes = f.read()

        # Парсим в зависимости от типа, вынося в отдельный поток
        loop = asyncio.get_running_loop()
        text = ""
        if file_name.lower().endswith(".pdf"):
            text = await loop.run_in_executor(None, partial(parse_pdf, file_content_bytes))
        elif file_name.lower().endswith(".docx"):
            text = await loop.run_in_executor(None, partial(parse_docx, file_content_bytes))

        # Валидируем и получаем саммари
        result = await report_validator.validate(text)

        # Формируем красивый ответ
        response_text = (
            f"{result['validation']}\n\n"
            f"--- 🏛️ Executive Summary ---\n"
            f"{result['summary']}"
        )
        await message.reply(response_text)

    except Exception as e:
        logging.error(f"Критическая ошибка при обработке файла {file_name}: {e}")
        await message.reply("Произошла непредвиденная ошибка. Попробуйте еще раз позже.")
    finally:
        # Гарантированно удаляем временный файл
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
            logging.info(f"Временный файл '{tmp_file_path}' удален.")


@router.message(F.text)
async def text_message_handler(message: Message) -> None:
    """
    Обработчик текстовых сообщений. Предлагает рерайтинг.
    """
    if not message.text:
        return

    await message.reply("Анализирую ваше сообщение...")

    result = await message_rewriter.rewrite(message.text)

    if result is None:
        await message.reply("К сожалению, не удалось обработать ваше сообщение. Попробуйте переформулировать его.")
        return

    if result.get("type") == "crisis":
        # Ответ для "плохих новостей"
        response_text = (
            f"🚨 {hbold('Протокол плохих новостей')}:\n\n"
            f"{result['text']}"
        )
        await message.answer(response_text)

    elif result.get("type") == "standard":
        # Стандартный ответ с двумя вариантами
        rewrite_data = result['data']
        response_text = (
            f"{hbold('Что исправлено:')}\n{rewrite_data['critique']}\n\n"
            f"{hbold('Вариант 1 (Строго-официальный):')}\n{rewrite_data['variant1']}\n\n"
            f"{hbold('Вариант 2 (Лаконично-деловой):')}\n{rewrite_data['variant2']}"
        )
        keyboard = create_rewrite_keyboard(rewrite_data['variant1'], rewrite_data['variant2'])
        await message.answer(response_text, reply_markup=keyboard)
    else:
        logging.warning(f"Получен неизвестный тип ответа от MessageRewriter: {result.get('type')}")
        await message.reply("Произошла внутренняя ошибка при обработке вашего сообщения.")


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
