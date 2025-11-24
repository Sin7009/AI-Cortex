# -*- coding: utf-8 -*-
"""
Главный исполнительный файл для запуска Telegram-бота 'Cortex'.
"""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from handlers import register_handlers
from services import initialize_services

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


async def on_startup() -> None:
    """
    Функция, выполняемая при запуске бота.
    Инициализирует все необходимые сервисы, в т.ч. базу данных.
    """
    logging.info("Бот запускается...")
    try:
        initialize_services()
        logging.info("Сервисы успешно инициализированы.")
    except Exception as e:
        logging.critical(f"Не удалось инициализировать сервисы: {e}", exc_info=True)
        # В реальном проекте здесь можно было бы остановить запуск,
        # но для простоты мы просто логируем критическую ошибку.


async def main() -> None:
    """
    Основная функция для запуска бота.
    """
    # Загружаем переменные окружения из .env файла
    load_dotenv()

    # Получаем токены из переменных окружения
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    model_provider = os.getenv("MODEL_PROVIDER", "ollama").lower()

    if not telegram_token:
        logging.critical(
            "Не найден TELEGRAM_BOT_TOKEN в .env файле! "
            "Убедитесь, что TELEGRAM_BOT_TOKEN установлен."
        )
        return
    
    # Проверка конфигурации для выбранного провайдера
    if model_provider == "gigachat":
        gigachat_key = os.getenv("GIGACHAT_API_KEY")
        if not gigachat_key:
            logging.critical(
                "MODEL_PROVIDER=gigachat, но GIGACHAT_API_KEY не найден в .env файле!"
            )
            return
    elif model_provider == "ollama":
        logging.info(
            "Используется Ollama. Убедитесь, что Ollama запущен (ollama serve) "
            "и модель загружена (ollama pull llama3.2)"
        )

    # Инициализация бота и диспетчера
    bot_properties = DefaultBotProperties(parse_mode=ParseMode.HTML)
    bot = Bot(token=telegram_token, default=bot_properties)
    dp = Dispatcher()

    # Регистрация обработчиков
    register_handlers(dp)

    # Добавляем задачу на запуск при старте
    dp.startup.register(on_startup)

    # Запускаем бота
    logging.info("Начинаем polling...")
    # Удаляем вебхук, если он был установлен ранее
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен вручную.")
    except Exception as e:
        logging.critical(f"Критическая ошибка при работе бота: {e}", exc_info=True)
