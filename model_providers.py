# -*- coding: utf-8 -*-
"""
Модуль для абстракции различных провайдеров моделей (внешние API и локальные модели).

Поддерживаемые провайдеры:
- GigaChat API (внешний, по умолчанию)
- Ollama (локальная модель)
- HuggingFace (локальная модель)
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
        """Асинхронно вызывает модель с промптом и возвращает ответ."""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Генерирует эмбеддинги для одного текстового запроса."""
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Генерирует эмбеддинги для списка документов."""
        pass


class GigaChatProvider(ModelProvider):
    """Провайдер для использования внешнего GigaChat API."""

    def __init__(self):
        try:
            from langchain_gigachat import GigaChat, GigaChatEmbeddings
            
            self.llm = GigaChat(
                credentials=os.getenv("GIGACHAT_API_KEY"),
                verify_ssl_certs=False,
                model="GigaChat-Pro"
            )
            self.embeddings = GigaChatEmbeddings(
                credentials=os.getenv("GIGACHAT_API_KEY"),
                verify_ssl_certs=False
            )
            logging.info("✅ GigaChat API провайдер успешно инициализирован")
        except Exception as e:
            logging.error(f"❌ Ошибка инициализации GigaChat API: {e}")
            raise

    async def ainvoke(self, prompt: str) -> str:
        """Асинхронно вызывает GigaChat API."""
        response = await self.llm.ainvoke(prompt)
        return response.content

    def embed_query(self, text: str) -> List[float]:
        """Генерирует эмбеддинги через GigaChat."""
        return self.embeddings.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Генерирует эмбеддинги для документов через GigaChat."""
        return self.embeddings.embed_documents(texts)


class OllamaProvider(ModelProvider):
    """Провайдер для использования локальной модели через Ollama."""

    def __init__(self, model_name: str = "llama3.2"):
        try:
            from langchain_ollama import ChatOllama, OllamaEmbeddings
            
            self.model_name = model_name
            self.llm = ChatOllama(model=self.model_name)
            self.embeddings = OllamaEmbeddings(model=self.model_name)
            logging.info(f"✅ Ollama провайдер успешно инициализирован с моделью: {self.model_name}")
        except ImportError:
            logging.error("❌ Пакет langchain-ollama не установлен. Установите: pip install langchain-ollama")
            raise
        except Exception as e:
            logging.error(f"❌ Ошибка инициализации Ollama: {e}. Убедитесь, что Ollama запущен локально.")
            raise

    async def ainvoke(self, prompt: str) -> str:
        """Асинхронно вызывает локальную модель через Ollama."""
        response = await self.llm.ainvoke(prompt)
        return response.content

    def embed_query(self, text: str) -> List[float]:
        """Генерирует эмбеддинги через Ollama."""
        return self.embeddings.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Генерирует эмбеддинги для документов через Ollama."""
        return self.embeddings.embed_documents(texts)


class HuggingFaceProvider(ModelProvider):
    """Провайдер для использования локальных моделей через HuggingFace."""

    def __init__(self, model_name: str = "IlyaGusev/saiga_llama3_8b"):
        try:
            from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
            from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
            import torch
            
            self.model_name = model_name
            self.device = 0 if torch.cuda.is_available() else -1
            
            # Инициализация LLM для генерации текста
            tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None
            )
            
            pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=1024,
                device=self.device
            )
            self.llm = HuggingFacePipeline(pipeline=pipe)
            
            # Инициализация эмбеддингов
            self.embeddings = HuggingFaceEmbeddings(
                model_name="intfloat/multilingual-e5-large",
                model_kwargs={'device': 'cuda' if torch.cuda.is_available() else 'cpu'}
            )
            
            logging.info(f"✅ HuggingFace провайдер успешно инициализирован с моделью: {self.model_name}")
            logging.info(f"   Использование GPU: {torch.cuda.is_available()}")
        except ImportError:
            logging.error("❌ Необходимые пакеты не установлены. Установите: pip install langchain-huggingface transformers torch")
            raise
        except Exception as e:
            logging.error(f"❌ Ошибка инициализации HuggingFace: {e}")
            raise

    async def ainvoke(self, prompt: str) -> str:
        """Асинхронно вызывает локальную модель HuggingFace."""
        import asyncio
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, self.llm.invoke, prompt)
        return response

    def embed_query(self, text: str) -> List[float]:
        """Генерирует эмбеддинги через HuggingFace."""
        return self.embeddings.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Генерирует эмбеддинги для документов через HuggingFace."""
        return self.embeddings.embed_documents(texts)


def get_model_provider() -> ModelProvider:
    """
    Фабричная функция для получения провайдера модели на основе переменной окружения.
    
    Переменная окружения MODEL_PROVIDER может принимать значения:
    - 'gigachat' (по умолчанию): Внешний GigaChat API
    - 'ollama': Локальная модель через Ollama
    - 'huggingface': Локальная модель через HuggingFace
    
    Returns:
        ModelProvider: Экземпляр выбранного провайдера
    """
    provider_type = os.getenv("MODEL_PROVIDER", "gigachat").lower()
    
    if provider_type == "ollama":
        model_name = os.getenv("OLLAMA_MODEL", "llama3.2")
        logging.info(f"📦 Использование локального провайдера: Ollama ({model_name})")
        return OllamaProvider(model_name=model_name)
    
    elif provider_type == "huggingface":
        model_name = os.getenv("HUGGINGFACE_MODEL", "IlyaGusev/saiga_llama3_8b")
        logging.info(f"📦 Использование локального провайдера: HuggingFace ({model_name})")
        return HuggingFaceProvider(model_name=model_name)
    
    else:  # по умолчанию gigachat
        logging.info("📦 Использование внешнего провайдера: GigaChat API")
        return GigaChatProvider()
