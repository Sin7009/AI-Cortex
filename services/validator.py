# -*- coding: utf-8 -*-
import asyncio
import logging
from model_providers import get_model_provider
from database.chroma_manager import VectorDBManager
from services.cognitive_layer import CognitiveScaffolder, ProblemType

class ReportValidator:
    """
    Сервис для проверки отчетов. Использует RAG для сравнения с эталонами.
    """
    def __init__(self, db_manager: VectorDBManager, model_provider=None):
        self.db_manager = db_manager

        if model_provider is None:
            model_provider = get_model_provider()
        self.model_provider = model_provider

        # Инициализация скаффолдера
        self.scaffolder = CognitiveScaffolder()

        logging.info("Сервис ReportValidator инициализирован.")

    async def _get_validation_result(self, report_text: str, context_report: str) -> str:
        """Асинхронно получает результат валидации структуры отчета."""
        if "Пример идеального отчета отсутствует" in context_report:
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

        # ВНЕДРЕНИЕ: Оборачиваем готовый промпт
        enhanced_prompt = self.scaffolder.enhance_prompt(prompt, ProblemType.DIAGNOSIS)

        response = await self.model_provider.ainvoke(enhanced_prompt)
        return response

    async def summarize(self, report_text: str) -> str:
        """Асинхронно генерирует Executive Summary для отчета."""
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
            logging.error(f"Ошибка при параллельном вызове API: {e}")
            return {
                "validation": "Произошла ошибка при анализе отчета.",
                "summary": "Не удалось сгенерировать саммари из-за ошибки."
            }
