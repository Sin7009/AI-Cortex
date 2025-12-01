# -*- coding: utf-8 -*-
"""
Модуль, содержащий основную бизнес-логику бота.

- ReportValidator: Сервис для валидации отчетов с использованием RAG.
- MessageRewriter: Сервис для рерайтинга сообщений с использованием LLM.
- VectorDBManager: Управляет созданием и наполнением векторной базы данных.
- Функции для парсинга файлов .pdf и .docx.
"""
import asyncio
import os
import logging
import re
import glob
from io import BytesIO

import chromadb
from docx import Document as DocxDocument
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

from mock_data import IDEAL_REPORTS, IDEAL_MESSAGES
from model_providers import get_model_provider

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

    def __init__(self, persist_directory: str, model_provider=None):
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        
        # Используем переданный провайдер или создаем новый
        if model_provider is None:
            model_provider = get_model_provider()
        self.model_provider = model_provider
        
        self.reports_collection = self.client.get_or_create_collection(name=REPORTS_COLLECTION)
        self.messages_collection = self.client.get_or_create_collection(name=MESSAGES_COLLECTION)
        logging.info(f"ChromaDB инициализирован в директории: {persist_directory}")

    def _populate_collection(self, collection, data: list[dict]):
        """Наполняет коллекцию данными с предварительной нарезкой (chunking)."""
        logging.info(f"Наполняем коллекцию '{collection.name}' с нарезкой...")

        # 1. Настраиваем нарезчик
        # chunk_size=1000: размер куска ~2-3 абзаца
        # chunk_overlap=200: перекрытие, чтобы не терять смысл на стыках
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""] # Стараемся резать по абзацам
        )

        all_splits = []
        all_ids = []
        all_metadatas = []

        for item in data:
            # Создаем чанки из одного документа
            # item["text"] берем из mock_data или файла
            chunks = text_splitter.split_text(item["text"])

            for i, chunk in enumerate(chunks):
                all_splits.append(chunk)
                # Уникальный ID для чанка: report_1_part_0, report_1_part_1...
                all_ids.append(f"{item['id']}_part_{i}")
                # В метаданных храним ID родительского документа, чтобы знать, откуда кусок
                all_metadatas.append({"source_id": item["id"]})

        # 2. Сохраняем кучу маленьких векторов вместо одного огромного
        # Батчами по 100 штук (для стабильности)
        batch_size = 100
        for i in range(0, len(all_splits), batch_size):
            end = min(i + batch_size, len(all_splits))
            collection.upsert(
                embeddings=self.model_provider.embed_documents(all_splits[i:end]),
                documents=all_splits[i:end],
                ids=all_ids[i:end],
                metadatas=all_metadatas[i:end]
            )

        logging.info(f"Коллекция '{collection.name}' обновлена. Обработано {len(all_splits)} чанков.")

    def load_real_data(self):
        """Загружает реальные файлы из папки knowledge_base."""
        # 1. Загрузка сообщений (Примеры стиля)
        real_messages = []
        for filepath in glob.glob("knowledge_base/messages/*.txt"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read()
                    real_messages.append({
                        "id": f"msg_{os.path.basename(filepath)}",
                        "text": text
                    })
            except Exception as e:
                logging.error(f"Ошибка при чтении файла сообщения {filepath}: {e}")

        if real_messages:
            self._populate_collection(self.messages_collection, real_messages)

        # 2. Загрузка отчетов (для валидации)
        real_reports = []
        for filepath in glob.glob("knowledge_base/reports/*.txt"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read()
                    real_reports.append({
                        "id": f"rep_{os.path.basename(filepath)}",
                        "text": text
                    })
            except Exception as e:
                logging.error(f"Ошибка при чтении файла отчета {filepath}: {e}")

        if real_reports:
            self._populate_collection(self.reports_collection, real_reports)

    def populate_databases(self):
        """Наполняет базы данных 'идеальными' отчетами и сообщениями."""
        # Наполняем mock-данными только если коллекции пусты
        if self.reports_collection.count() == 0:
            logging.info("Инициализация mock-данных для отчетов...")
            self._populate_collection(self.reports_collection, IDEAL_REPORTS)

        if self.messages_collection.count() == 0:
            logging.info("Инициализация mock-данных для сообщений...")
            self._populate_collection(self.messages_collection, IDEAL_MESSAGES)

        # Загрузка реальных данных (выполняется всегда для обновления)
        logging.info("Проверка и загрузка реальных данных...")
        self.load_real_data()

    def query_reports(self, text: str, n_results: int = 1) -> list[str]:
        """Ищет похожие документы в коллекции отчетов."""
        query_embedding = self.model_provider.embed_query(text)
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
    def __init__(self, db_manager: VectorDBManager, model_provider=None):
        self.db_manager = db_manager
        
        # Используем переданный провайдер или создаем новый
        if model_provider is None:
            model_provider = get_model_provider()
        self.model_provider = model_provider
        
        logging.info("Сервис ReportValidator инициализирован.")

    async def _get_validation_result(self, report_text: str, context_report: str) -> str:
        """Асинхронно получает результат валидации структуры отчета."""
        if "Пример идеального отчета отсутствует" in context_report:
            # Упрощенный промпт, если RAG ничего не нашел
            prompt = f"""
            Ты — строгий и опытный редактор, анализирующий отчеты для CEO.
            Твоя задача — оценить предоставленный отчет на основе ключевых критериев. База знаний для сравнения сейчас недоступна.

            **Критерии оценки:**
            1.  Наличие ключевых разделов: "Введение", "Методология", "Инсайты", "Выводы".
            2.  Общая структура, логика и ясность изложения.

            **Отчет для анализа:**
            ---
            {report_text}
            ---

            **Твой вердикт (без сравнения с примером):**
            Напиши свой ответ в следующем формате:
            **Статус:** [здесь напиши "Прошел" или "Требует доработки"]
            **Краткий анализ:** [здесь напиши 2-3 предложения с объяснением, что хорошо или что нужно улучшить, основываясь только на структуре и логике]
            """
        else:
            # Стандартный промпт с RAG-контекстом
            prompt = f"""
            Ты — строгий и опытный редактор, анализирующий отчеты для CEO.
            Твоя задача — оценить предоставленный отчет на основе следующих критериев:
            1.  Наличие ключевых разделов: "Введение", "Методология", "Инсайты", "Выводы".
            2.  Общая структура и логика изложения.
            3.  Сравнение с наиболее релевантным фрагментом из нашей базы знаний.

            **Релевантный фрагмент из эталонного отчета:**
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
        response = await self.model_provider.ainvoke(prompt)
        return response

    async def summarize(self, report_text: str) -> str:
        """Асинхронно генерирует Executive Summary для отчета."""
        # Ограничиваем входной текст, чтобы не упасть по токенам
        # Берем первые 15000 символов (примерно 4-5 страниц текста)
        # Для MVP этого достаточно, так как суть часто в начале.
        safe_text = report_text[:15000]
        if len(report_text) > 15000:
            safe_text += "\n\n[...Текст обрезан для анализа...]"

        prompt = f"""
        Ты — старший бизнес-аналитик, который готовит выжимку из отчета для CEO.
        У тебя есть всего 30 секунд его внимания. Твоя задача — извлечь самую суть.

        **Инструкции:**
        1. Прочитай "Текст отчета".
        2. Выдели **3 главных риска** и **3 главные возможности** (или ключевых вывода), которые в нем описаны.
        3. Сформулируй их максимально коротко и ясно.
        4. Если рисков или возможностей меньше трех (или нет совсем), укажи это.
        5. Твой ответ должен быть только в формате списка, без вступлений.

        **Текст отчета:**
        ---
        {safe_text}
        ---

        **Твой ответ:**
        """
        response = await self.model_provider.ainvoke(prompt)
        return response

    async def validate(self, report_text: str) -> dict[str, str]:
        """
        Проверяет отчет и генерирует саммари, возвращая словарь с результатами.
        """
        if not report_text.strip():
            return {
                "validation": "Отчет пуст. Пожалуйста, загрузите файл с текстом.",
                "summary": "Невозможно создать саммари для пустого отчета."
            }

        # RAG: Находим самый похожий "идеальный" чанк в отдельном потоке
        # Используем только начало текста для поиска, чтобы ускорить процесс
        # и избежать "засорения" запроса деталями из середины документа.
        query_text = report_text[:4000]
        loop = asyncio.get_running_loop()
        similar_report_chunks = await loop.run_in_executor(
            None,
            self.db_manager.query_reports,
            query_text,
            1
        )
        context_report = similar_report_chunks[0] if similar_report_chunks else "Пример идеального отчета отсутствует."

        try:
            logging.info("Одновременная отправка запросов на валидацию и саммари...")
            validation_result, summary_result = await asyncio.gather(
                self._get_validation_result(report_text, context_report),
                self.summarize(report_text)
            )
            logging.info("Получены ответы на оба запроса.")
            return {"validation": validation_result, "summary": summary_result}

        except Exception as e:
            logging.error(f"Ошибка при параллельном вызове GigaChat API: {e}")
            return {
                "validation": "Произошла ошибка при анализе отчета.",
                "summary": "Не удалось сгенерировать саммари из-за ошибки."
            }


class MessageRewriter:
    """
    Сервис для рерайтинга сообщений. Использует LLM для критики и предложения вариантов.
    """
    def __init__(self, db_manager: VectorDBManager, model_provider=None):
        # !!! ВАЖНО: Мы теперь требуем db_manager
        self.db_manager = db_manager
        if model_provider is None:
            model_provider = get_model_provider()
        self.model_provider = model_provider
        logging.info("Сервис MessageRewriter инициализирован.")

    def _is_crisis_communication(self, message_text: str) -> bool:
        """Определяет, содержит ли сообщение признаки 'плохих новостей'."""
        crisis_keywords = [
            "проблема", "задержка", "сбой", "срыв", "риск",
            "не успеваем", "не получается", "сломалось", "ошибка", "факап"
        ]
        text_lower = message_text.lower()
        return any(keyword in text_lower for keyword in crisis_keywords)

    async def _rewrite_crisis_message(self, message_text: str) -> str:
        """Переписывает 'кризисное' сообщение по строгому шаблону."""
        prompt = f"""
        Ты — элитный ассистент CEO, специалист по кризисным коммуникациям.
        Твоя задача — преобразовать эмоциональное и размытое сообщение о проблеме в четкий, структурированный "военный доклад".

        **Инструкции:**
        1.  Проанализируй "Оригинальный текст". Убери всю "воду", оправдания и эмоции.
        2.  Извлеки только суть.
        3.  Сформируй ответ строго по шаблону из 4-х пунктов. Если какой-то информации нет в оригинале, напиши "Не указано".

        **Шаблон:**
        **Факт:** [Что именно случилось? Кратко и без эмоций.]
        **Причина:** [Почему это произошло? Коротко.]
        **Решение:** [Что уже делается для исправления ситуации?]
        **Помощь:** [Какая помощь требуется от руководителя прямо сейчас?]

        **Оригинальный текст:**
        ---
        {message_text}
        ---

        **Твой ответ (строго по шаблону):**
        """
        response = await self.model_provider.ainvoke(prompt)
        return response

    async def rewrite(self, message_text: str) -> dict | None:
        """
        Анализирует и переписывает сообщение, используя стандартный или кризисный протокол.
        """
        if self._is_crisis_communication(message_text):
            logging.info("Обнаружено кризисное сообщение. Активирован 'Протокол плохих новостей'.")
            try:
                rewritten_text = await self._rewrite_crisis_message(message_text)
                return {"type": "crisis", "text": rewritten_text}
            except Exception as e:
                logging.error(f"Ошибка при рерайте кризисного сообщения: {e}")
                return None

        # Стандартная логика рерайта

        # 1. ДОСТАЕМ ПРИМЕРЫ (Few-Shot)
        # Ищем 3 ближайших идеальных сообщения из базы
        loop = asyncio.get_running_loop()
        try:
             # Эмбеддинг запроса для поиска похожих по стилю/смыслу
            # query_embedding = self.model_provider.embed_query(message_text) # Убрали блокирующий вызов

            # Вся тяжелая работа (эмбеддинг + поиск) теперь в отдельном потоке
            results = await loop.run_in_executor(
                None,
                lambda: self.db_manager.messages_collection.query(
                    query_embeddings=[self.model_provider.embed_query(message_text)],
                    n_results=3
                )
            )
            examples_list = results['documents'][0] if results['documents'] else []
            examples_text = "\n---\n".join(examples_list)
        except Exception as e:
            logging.error(f"Ошибка получения примеров RAG: {e}")
            examples_text = "Примеры недоступны."

        logging.info("Стандартное сообщение. Генерация двух вариантов.")

        # 2. ОБНОВЛЕННЫЙ ПРОМПТ С ПРИМЕРАМИ
        prompt = f"""
        Ты — ассистент руководителя. Твоя задача — переписать сообщение пользователя, опираясь на ПРИМЕРЫ ИДЕАЛЬНОГО СТИЛЯ (ниже).

        **Примеры того, как НАДО писать (Только для стиля, не копируй их текст!):**
        ---
        {examples_text}
        ---

        **Инструкции:**
        1. Проанализируй "Оригинальный текст" (внизу).
        2. Перепиши его в двух вариантах, подражая стилю из примеров выше.
        3. Не выдумывай факты.
        4. Не используй слова вроде "Господин", используй Имя Отчество.
        5. НИКАКОГО ВСТУПИТЕЛЬНОГО ТЕКСТА (например "Вот варианты..."). СРАЗУ выдавай результат по шаблону.

        **Пример ожидаемого формата ответа:**
        [START]
        **Что исправлено:**
        - Убрана пассивная агрессия
        - Исправлено обращение

        **Вариант 1 (Строго-официальный):**
        Андрей Владимирович, здравствуйте. Отчет во вложении.

        **Вариант 2 (Лаконично-деловой):**
        Андрей Владимирович, направляю отчет.
        [END]

        **Оригинальный текст:**
        ---
        {message_text}
        ---

        **Твой ответ (Только JSON-подобный текст, без лишних слов):**
        """
        try:
            logging.info("Отправка запроса в LLM для рерайтинга сообщения...")
            response = await self.model_provider.ainvoke(prompt)
            logging.info("Получен ответ от LLM.")
            parsed_data = self._parse_rewrite_response(response)
            if parsed_data:
                return {"type": "standard", "data": parsed_data}
            return None
        except Exception as e:
            logging.error(f"Ошибка при вызове LLM API: {e}")
            return None

    def _parse_rewrite_response(self, response_text: str) -> dict[str, str] | None:
        """Парсит ответ от LLM с помощью Regex для большей надежности."""
        try:
            # Убираем маркеры и лишние пробелы
            text = response_text.replace("[START]", "").replace("[END]", "").strip()

            # Паттерн ищет разделы, допуская небольшие вариации в форматировании
            # Добавлена гибкость: (?i) ignore case, опциональные заголовки
            pattern = (
                r"(?si)"
                r"(?:Что исправлено:?\s*(?P<critique>.*?)\s*)?" # Делаем критику опциональной, если модель пропустит
                r"(?:(?:\*\*|###)\s*Вариант 1.*?:?\s*(?:\*\*|###)?\s*(?P<v1>.*?)\s*)"
                r"(?:(?:\*\*|###)\s*Вариант 2.*?:?\s*(?:\*\*|###)?\s*(?P<v2>.*)$)"
            )

            match = re.search(pattern, text)
            if not match:
                logging.warning(f"Regex не сматчил ответ: {text[:100]}...")
                # Попытка найти хотя бы что-то похожее на текст, если формат совсем сломан
                # Но лучше вернуть None, чтобы пользователь увидел ошибку, чем мусор.
                return None

            return {
                "critique": match.group("critique").strip(),
                "variant1": match.group("v1").strip(),
                "variant2": match.group("v2").strip()
            }
        except Exception as e:
            logging.error(f"Ошибка парсинга RegEx: {e}")
            return None


# ---- Инициализация сервисов ----
# Получаем провайдер модели на основе конфигурации
model_provider = get_model_provider()

# Создаем единственный экземпляр менеджера БД с провайдером модели
db_manager = VectorDBManager(persist_directory=CHROMA_PERSIST_DIRECTORY, model_provider=model_provider)

# Создаем экземпляры сервисов, передавая им менеджер БД и провайдер модели
report_validator = ReportValidator(db_manager, model_provider=model_provider)
message_rewriter = MessageRewriter(db_manager=db_manager, model_provider=model_provider)

# Функция для первоначального наполнения БД
def initialize_services():
    """
    Выполняет все необходимые действия при старте бота:
    - Наполняет векторную базу данных.
    """
    logging.info("Запуск инициализации сервисов...")
    db_manager.populate_databases()
    logging.info("Инициализация сервисов завершена.")
