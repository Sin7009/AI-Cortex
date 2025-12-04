# -*- coding: utf-8 -*-
import asyncio
import logging
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from model_providers import get_model_provider
from database.chroma_manager import VectorDBManager
from services.cognitive_layer import CognitiveScaffolder, ProblemType

# 1. Определяем структуру ответа
class RewriteResponse(BaseModel):
    critique: str = Field(description="Краткий анализ того, что было исправлено в оригинальном тексте")
    variant1: str = Field(description="Вариант текста в строго-официальном стиле")
    variant2: str = Field(description="Вариант текста в лаконично-деловом стиле")

class MessageRewriter:
    """
    Сервис для рерайтинга сообщений. Использует LLM для критики и предложения вариантов.
    """
    def __init__(self, db_manager: VectorDBManager, model_provider=None):
        self.db_manager = db_manager
        if model_provider is None:
            model_provider = get_model_provider()
        self.model_provider = model_provider

        # Инициализируем парсер
        self.parser = PydanticOutputParser(pydantic_object=RewriteResponse)

        # Инициализация скаффолдера
        self.scaffolder = CognitiveScaffolder()

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
        loop = asyncio.get_running_loop()
        try:
             # Эмбеддинг запроса для поиска похожих по стилю/смыслу
             # Вся тяжелая работа (эмбеддинг + поиск) в отдельном потоке
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

        # Получаем инструкции по формату от парсера
        format_instructions = self.parser.get_format_instructions()

        # 2. ПРОМПТ С ПРИМЕРАМИ И ИНСТРУКЦИЯМИ
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

        {format_instructions}

        **Оригинальный текст:**
        ---
        {message_text}
        ---
        """

        # ВНЕДРЕНИЕ: Оборачиваем промпт в Design-протокол
        enhanced_prompt = self.scaffolder.enhance_prompt(prompt, ProblemType.DESIGN)

        try:
            logging.info("Отправка запроса в LLM для рерайтинга сообщения...")
            response = await self.model_provider.ainvoke(enhanced_prompt)
            logging.info("Получен ответ от LLM.")

            # Парсим JSON-ответ в объект Pydantic
            parsed_obj = self.parser.parse(response)
            return {
                "type": "standard",
                "data": parsed_obj.model_dump()
            }
        except Exception as e:
            logging.error(f"Ошибка при вызове LLM API или парсинге: {e}")
            return None
