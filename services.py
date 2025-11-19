# -*- coding: utf-8 -*-
"""
Модуль, содержащий основную бизнес-логику бота.

- ReportValidator: Сервис для валидации отчетов с использованием RAG.
- MessageRewriter: Сервис для рерайтинга сообщений с использованием LLM.
- VectorDBManager: Управляет созданием и наполнением векторной базы данных.
- Функции для парсинга файлов .pdf и .docx.
"""
import os
import logging
from io import BytesIO

import chromadb
from docx import Document as DocxDocument
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_gigachat import GigaChat, GigaChatEmbeddings
from dotenv import load_dotenv

from mock_data import IDEAL_REPORTS, IDEAL_MESSAGES

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---- Константы ----
CHROMA_PERSIST_DIRECTORY = "chroma_db"
REPORTS_COLLECTION = "reports"
MESSAGES_COLLECTION = "messages"


# ---- Функции парсинга файлов ----
def parse_pdf(file_content: bytes) -> str:
    """Извлекает текст из содержимого PDF-файла."""
    try:
        pdf_file = BytesIO(file_content)
        reader = PdfReader(pdf_file)
        text = "".join(page.extract_text() for page in reader.pages)
        if not text:
            logging.warning("Не удалось извлечь текст из PDF. Возможно, это PDF-изображение.")
            return ""
        return text
    except Exception as e:
        logging.error(f"Ошибка при парсинге PDF: {e}")
        raise ValueError("Не удалось обработать PDF-файл.")


def parse_docx(file_content: bytes) -> str:
    """Извлекает текст из содержимого DOCX-файла."""
    try:
        doc_file = BytesIO(file_content)
        doc = DocxDocument(doc_file)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        if not text:
            logging.warning("DOCX-файл пуст.")
        return text
    except Exception as e:
        logging.error(f"Ошибка при парсинге DOCX: {e}")
        raise ValueError("Не удалось обработать DOCX-файл.")


# ---- Управление векторной базой данных ----
class VectorDBManager:
    """
    Управляет инициализацией и работой с векторной базой данных ChromaDB.
    """

    def __init__(self, persist_directory: str):
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        self.embeddings_model = GigaChatEmbeddings(
            credentials=os.getenv("GIGACHAT_API_KEY"),
            verify_ssl_certs=False
        )
        self.reports_collection = self.client.get_or_create_collection(name=REPORTS_COLLECTION)
        self.messages_collection = self.client.get_or_create_collection(name=MESSAGES_COLLECTION)
        logging.info(f"ChromaDB инициализирован в директории: {persist_directory}")

    def _populate_collection(self, collection, data: list[dict]):
        """Наполняет коллекцию данными, если она пуста."""
        if collection.count() > 0:
            logging.info(f"Коллекция '{collection.name}' уже наполнена. Пропускаем.")
            return

        logging.info(f"Наполняем коллекцию '{collection.name}'...")
        documents = [item["text"] for item in data]
        ids = [item["id"] for item in data]

        # Генерируем эмбеддинги
        embeddings = self.embeddings_model.embed_documents(documents)

        collection.add(
            embeddings=embeddings,
            documents=documents,
            ids=ids
        )
        logging.info(f"Коллекция '{collection.name}' успешно наполнена. Добавлено {len(ids)} документов.")

    def populate_databases(self):
        """Наполняет базы данных 'идеальными' отчетами и сообщениями."""
        self._populate_collection(self.reports_collection, IDEAL_REPORTS)
        self._populate_collection(self.messages_collection, IDEAL_MESSAGES)

    def query_reports(self, text: str, n_results: int = 1) -> list[str]:
        """Ищет похожие документы в коллекции отчетов."""
        query_embedding = self.embeddings_model.embed_query(text)
        results = self.reports_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        return results['documents'][0] if results['documents'] else []


# ---- Сервисы для бизнес-логики ----
class ReportValidator:
    """
    Сервис для проверки отчетов. Использует RAG для сравнения с эталонами.
    """
    def __init__(self, db_manager: VectorDBManager):
        self.db_manager = db_manager
        self.llm = GigaChat(
            credentials=os.getenv("GIGACHAT_API_KEY"),
            verify_ssl_certs=False,
            model="GigaChat-Pro"
        )
        logging.info("Сервис ReportValidator инициализирован.")

    async def validate(self, report_text: str) -> str:
        """
        Проверяет отчет, используя RAG и LLM для анализа.
        """
        if not report_text.strip():
            return "Отчет пуст. Пожалуйста, загрузите файл с текстом."

        # 1. RAG: Находим самый похожий "идеальный" отчет
        similar_report_texts = self.db_manager.query_reports(report_text, n_results=1)
        if not similar_report_texts:
            logging.warning("Не найдено похожих отчетов в базе знаний.")
            # Если ничего не найдено, работаем без примера
            context_report = "Пример идеального отчета отсутствует."
        else:
            context_report = similar_report_texts[0]

        # 2. LLM Analysis: Формируем промпт и отправляем в GigaChat
        prompt = f"""
        Ты — строгий и опытный редактор, анализирующий отчеты для CEO.
        Твоя задача — оценить предоставленный отчет на основе следующих критериев:
        1.  Наличие ключевых разделов: "Введение", "Методология", "Инсайты", "Выводы".
        2.  Общая структура и логика изложения.
        3.  Сравнение с эталонным примером.

        **Эталонный пример отчета:**
        ---
        {context_report}
        ---

        **Отчет для анализа:**
        ---
        {report_text}
        ---

        **Твой вердикт:**
        Напиши свой ответ в следующем формате:
        **Статус:** [здесь напиши "Прошел" или "Требует доработки"]
        **Краткий анализ:** [здесь напиши 2-3 предложения с объяснением, что хорошо или что нужно улучшить, основываясь на критериях и сравнении с эталоном]
        """

        try:
            logging.info("Отправка запроса в GigaChat для валидации отчета...")
            response = await self.llm.ainvoke(prompt)
            logging.info("Получен ответ от GigaChat.")
            return response.content
        except Exception as e:
            logging.error(f"Ошибка при вызове GigaChat API: {e}")
            return "Произошла ошибка при анализе отчета. Попробуйте позже."


class MessageRewriter:
    """
    Сервис для рерайтинга сообщений. Использует LLM для критики и предложения вариантов.
    """
    def __init__(self):
        self.llm = GigaChat(
            credentials=os.getenv("GIGACHAT_API_KEY"),
            verify_ssl_certs=False,
            model="GigaChat-Pro"
        )
        logging.info("Сервис MessageRewriter инициализирован.")

    async def rewrite(self, message_text: str) -> dict[str, str] | None:
        """
        Анализирует и переписывает сообщение, предлагая два варианта.
        """
        prompt = f"""
        Ты — ассистент руководителя, мастер деловой переписки. Твоя задача — помочь пользователю улучшить черновик его сообщения для CEO.

        **Инструкции:**
        1.  Проанализируй "Оригинальный текст" на предмет "воды", излишних эмоций, панибратства и нечетких формулировок.
        2.  Сформируй блок "Что исправлено:", где кратко (2-3 пункта) перечисли основные проблемы оригинала.
        3.  Создай ДВА улучшенных варианта текста:
            -   **Вариант 1 (Строго-официальный):** Максимально формальный, сухой и уважительный стиль.
            -   **Вариант 2 (Лаконично-деловой):** Краткий, энергичный, по делу, но все еще уважительный стиль.
        4.  Отформатируй свой ответ строго по шаблону ниже, без каких-либо вступлений или заключений.

        **Оригинальный текст:**
        ---
        {message_text}
        ---

        **Твой ответ (строго по шаблону):**
        [START]
        **Что исправлено:**
        - [Проблема 1]
        - [Проблема 2]

        **Вариант 1 (Строго-официальный):**
        [Текст варианта 1]

        **Вариант 2 (Лаконично-деловой):**
        [Текст варианта 2]
        [END]
        """
        try:
            logging.info("Отправка запроса в GigaChat для рерайтинга сообщения...")
            response = await self.llm.ainvoke(prompt)
            logging.info("Получен ответ от GigaChat.")
            return self._parse_rewrite_response(response.content)
        except Exception as e:
            logging.error(f"Ошибка при вызове GigaChat API: {e}")
            return None

    def _parse_rewrite_response(self, response_text: str) -> dict[str, str] | None:
        """Парсит ответ от LLM, разделяя его на составные части."""
        try:
            # Очищаем ответ от возможных маркеров начала/конца
            clean_text = response_text.replace("[START]", "").replace("[END]", "").strip()

            critique_part, rest = clean_text.split("**Вариант 1 (Строго-официальный):**", 1)
            variant1_part, variant2_part = rest.split("**Вариант 2 (Лаконично-деловой):**", 1)

            critique = critique_part.replace("**Что исправлено:**", "").strip()
            variant1 = variant1_part.strip()
            variant2 = variant2_part.strip()

            return {
                "critique": critique,
                "variant1": variant1,
                "variant2": variant2
            }
        except ValueError as e:
            logging.error(f"Не удалось распарсить ответ LLM: {e}\nОтвет: {response_text}")
            return None


# ---- Инициализация сервисов ----
# Создаем единственный экземпляр менеджера БД
db_manager = VectorDBManager(persist_directory=CHROMA_PERSIST_DIRECTORY)

# Создаем экземпляры сервисов, передавая им менеджер БД
report_validator = ReportValidator(db_manager)
message_rewriter = MessageRewriter()

# Функция для первоначального наполнения БД
def initialize_services():
    """
    Выполняет все необходимые действия при старте бота:
    - Наполняет векторную базу данных.
    """
    logging.info("Запуск инициализации сервисов...")
    db_manager.populate_databases()
    logging.info("Инициализация сервисов завершена.")
