# -*- coding: utf-8 -*-
"""
Модуль для абстракции различных провайдеров моделей.
"""
import os
import logging
from abc import ABC, abstractmethod
from typing import List

from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class ModelProvider(ABC):
    """Абстрактный базовый класс для провайдеров моделей."""

    @abstractmethod
    async def ainvoke(self, prompt: str) -> str:
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass


class OpenRouterProvider(ModelProvider):
    """
    Провайдер для OpenRouter (Grok, Claude, GPT и др.).
    Использует API OpenRouter для генерации текста и локальную модель HuggingFace для эмбеддингов.
    """
    def __init__(self):
        try:
            from langchain_openai import ChatOpenAI
            from langchain_huggingface import HuggingFaceEmbeddings
            import torch

            # 1. Настройка LLM (Grok)
            api_key = os.getenv("OPENROUTER_API_KEY")
            model_name = os.getenv("OPENROUTER_MODEL", "x-ai/grok-4.1-fast:free")
            
            if not api_key:
                raise ValueError("Не найден OPENROUTER_API_KEY в .env")

            self.llm = ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                model=model_name,
                temperature=0.2, # Низкая температура для строгости
                # Важно для OpenRouter: передаем заголовки, чтобы они знали источник
                default_headers={
                    "HTTP-Referer": "https://github.com/ai-cortex",
                    "X-Title": "AI Cortex Bot"
                }
            )

            # 2. Настройка Эмбеддингов (Локально, бесплатно и качественно)
            # Используем E5-Large — одну из лучших моделей для русского языка
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logging.info(f"⏳ Загрузка модели эмбеддингов на {device}...")

            self.embeddings = HuggingFaceEmbeddings(
                model_name="intfloat/multilingual-e5-large",
                model_kwargs={'device': device}
            )

            logging.info(f"✅ OpenRouter провайдер готов: {model_name} + E5-Embeddings")

        except ImportError:
            logging.error("❌ Не установлены пакеты. Выполните: pip install langchain-openai langchain-huggingface sentence-transformers")
            raise
        except Exception as e:
            logging.error(f"❌ Ошибка инициализации OpenRouter: {e}")
            raise

    async def ainvoke(self, prompt: str) -> str:
        response = await self.llm.ainvoke(prompt)
        return response.content

    def embed_query(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embeddings.embed_documents(texts)


# --- Старые провайдеры оставляем для совместимости ---

class GigaChatProvider(ModelProvider):
    def __init__(self):
        try:
            from langchain_gigachat import GigaChat, GigaChatEmbeddings
            self.llm = GigaChat(credentials=os.getenv("GIGACHAT_API_KEY"), verify_ssl_certs=False, model="GigaChat-Pro")
            self.embeddings = GigaChatEmbeddings(credentials=os.getenv("GIGACHAT_API_KEY"), verify_ssl_certs=False)
            logging.info("✅ GigaChat API провайдер успешно инициализирован")
        except Exception as e:
            logging.error(f"❌ Ошибка GigaChat: {e}")
            raise

    async def ainvoke(self, prompt: str) -> str:
        response = await self.llm.ainvoke(prompt)
        return response.content

    def embed_query(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embeddings.embed_documents(texts)

class OllamaProvider(ModelProvider):
    def __init__(self, model_name: str = None):
        try:
            from langchain_ollama import ChatOllama, OllamaEmbeddings
            self.model_name = model_name or os.getenv("OLLAMA_MODEL", "llama3.2")
            self.llm = ChatOllama(model=self.model_name, temperature=0.2)
            self.embeddings = OllamaEmbeddings(model=self.model_name)
            logging.info(f"✅ Ollama провайдер успешно инициализирован: {self.model_name}")
        except Exception as e:
            logging.error(f"❌ Ошибка Ollama: {e}")
            raise

    async def ainvoke(self, prompt: str) -> str:
        response = await self.llm.ainvoke(prompt)
        return response.content

    def embed_query(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embeddings.embed_documents(texts)


def get_model_provider() -> ModelProvider:
    """Фабрика провайдеров."""
    provider_type = os.getenv("MODEL_PROVIDER", "openrouter").lower()
    
    if provider_type == "openrouter":
        return OpenRouterProvider()
    
    elif provider_type == "gigachat":
        return GigaChatProvider()
    
    elif provider_type == "ollama":
        return OllamaProvider()
    
    else:
        # Fallback или HuggingFace (если нужно вернуть, добавь класс обратно)
        logging.warning(f"Провайдер {provider_type} не найден, переключаемся на OpenRouter")
        return OpenRouterProvider()
