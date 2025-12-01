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
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from handlers import register_handlers
from middlewares.auth import AuthMiddleware
from model_providers import get_model_provider
from database.chroma_manager import VectorDBManager
from services.validator import ReportValidator
from services.rewriter import MessageRewriter

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Глобальные переменные для сервисов (чтобы on_startup имел к ним доступ или инициализировал их)
db_manager = None
report_validator = None
message_rewriter = None

async def initialize_app_services():
    """
    Инициализирует сервисы приложения.
    """
    global db_manager, report_validator, message_rewriter

    # Загружаем переменные окружения
    load_dotenv()

    # 1. Провайдер модели
    model_provider = get_model_provider()

    # 2. База данных
    # Убедимся, что директории созданы
    os.makedirs("chroma_db", exist_ok=True)
    os.makedirs("knowledge_base", exist_ok=True)

    db_manager = VectorDBManager(persist_directory="chroma_db", model_provider=model_provider)

    # 3. Наполнение базы (синхронно или в треде, но ChromaDB клиент обычно синхронный)
    # Здесь populate_databases делает тяжелую работу
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, db_manager.populate_databases)

    # 4. Бизнес-сервисы
    report_validator = ReportValidator(db_manager, model_provider=model_provider)
    message_rewriter = MessageRewriter(db_manager=db_manager, model_provider=model_provider)

    logging.info("Сервисы успешно инициализированы.")
    return report_validator, message_rewriter


async def main() -> None:
    """
    Основная функция для запуска бота.
    """
    # Загружаем переменные окружения из .env файла
    load_dotenv()

    # Получаем токены из переменных окружения
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    bot_password = os.getenv("BOT_PASSWORD", "secret123") # Дефолтный пароль, если не задан

    if not telegram_token:
        logging.critical(
            "Не найден TELEGRAM_BOT_TOKEN в .env файле! "
            "Убедитесь, что TELEGRAM_BOT_TOKEN установлен."
        )
        return

    # Инициализация бота и диспетчера
    bot_properties = DefaultBotProperties(parse_mode=ParseMode.HTML)
    bot = Bot(token=telegram_token, default=bot_properties)

    # Используем MemoryStorage для FSM (хранение состояний авторизации)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Регистрируем Middleware авторизации
    auth_middleware = AuthMiddleware(password=bot_password)
    dp.message.outer_middleware(auth_middleware)

    # Инициализируем сервисы перед запуском
    logging.info("Инициализация сервисов...")
    try:
        validator, rewriter = await initialize_app_services()
    except Exception as e:
        logging.critical(f"Ошибка инициализации сервисов: {e}", exc_info=True)
        return

    # Регистрация обработчиков с передачей сервисов
    register_handlers(dp, validator, rewriter)

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
