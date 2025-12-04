# -*- coding: utf-8 -*-
from enum import Enum

class ProblemType(Enum):
    DIAGNOSIS = "diagnosis"   # Для валидации отчетов (анализ, критика, поиск ошибок)
    DESIGN = "design"         # Для рерайтинга (написание, улучшение стиля, творчество)

class CognitiveScaffolder:
    """
    Внедряет структуры успешного мышления (Reasoning Structures) в промпты.
    Основано на: arXiv:2511.16660v2 [cs.AI], Table 1 & Section 4.

    Метод: Test-time reasoning guidance. Мы принуждаем модель пройти
    по успешному графу рассуждений (Reasoning Graph) перед генерацией ответа.
    """

    def __init__(self):
        self._patterns = {
            # Паттерн для анализа (Diagnosis-Solution)
            # Успешный трек из статьи: Strategy -> Hierarchy -> Knowledge -> Verification
            ProblemType.DIAGNOSIS: (
                "\n=== COGNITIVE REASONING PROTOCOL (DIAGNOSIS) ===\n"
                "Прежде чем выдать вердикт, ты ОБЯЗАН пройти следующие этапы мышления (Internal Monologue):\n"
                "1. [Strategy Selection]: Определи жанр документа и строгость проверки. Какую стратегию анализа выбрать?\n"
                "2. [Hierarchical Organization]: Ментально разбей отчет на логические блоки (Введение -> Доказательства -> Выводы). "
                "Есть ли разрывы в этой цепочке?\n"
                "3. [Knowledge Alignment]: Сравни содержимое с общепринятыми стандартами бизнес-отчетов или эталоном.\n"
                "4. [Verification]: Проверь факты на внутреннюю непротиворечивость. Подтверждаются ли выводы данными?\n"
                "================================================\n"
                "ВАЖНО: В финальном ответе НЕ пиши эти шаги. Используй результаты этого анализа "
                "только для формирования максимально точного статуса и критики.\n"
            ),

            # Паттерн для написания (Design/Creative)
            # Успешный трек из статьи: Goal Management -> Conceptual Processing -> Compositionality -> Evaluation
            ProblemType.DESIGN: (
                "\n=== COGNITIVE REASONING PROTOCOL (DESIGN) ===\n"
                "Прежде чем переписать текст, выполни ментальную работу:\n"
                "1. [Goal Management]: Какую именно реакцию мы хотим вызвать у читателя? (Уверенность, спокойствие, действие?)\n"
                "2. [Conceptual Processing]: Выдели ключевой смысл сообщения, отбросив 'воду', эмоции и канцеляризмы.\n"
                "3. [Compositionality]: Собери текст заново. Используй сильные глаголы. Обеспечь связность предложений.\n"
                "4. [Evaluation]: Прочитай результат глазами получателя. Звучит ли это профессионально? Нет ли двусмысленности?\n"
                "=============================================\n"
                "Используй эти выводы для генерации двух идеальных вариантов текста.\n"
            )
        }

    def enhance_prompt(self, base_prompt: str, problem_type: ProblemType) -> str:
        """Оборачивает базовый промпт в когнитивный каркас."""
        scaffold = self._patterns.get(problem_type, "")
        # Добавляем инструкцию в конец промпта, чтобы она была "свежей" в контексте
        return f"{base_prompt}\n{scaffold}"
