# -*- coding: utf-8 -*-
import glob
import logging
import os
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from mock_data import IDEAL_REPORTS, IDEAL_MESSAGES
from model_providers import get_model_provider

# ---- Константы ----
CHROMA_PERSIST_DIRECTORY = "chroma_db"
REPORTS_COLLECTION = "reports"
MESSAGES_COLLECTION = "messages"

class VectorDBManager:
    """
    Управляет инициализацией и работой с векторной базой данных ChromaDB.
    """

    def __init__(self, persist_directory: str = CHROMA_PERSIST_DIRECTORY, model_provider=None):
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
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )

        all_splits = []
        all_ids = []
        all_metadatas = []

        for item in data:
            chunks = text_splitter.split_text(item["text"])

            for i, chunk in enumerate(chunks):
                all_splits.append(chunk)
                all_ids.append(f"{item['id']}_part_{i}")
                all_metadatas.append({"source_id": item["id"]})

        # 2. Сохраняем кучу маленьких векторов
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
        # 1. Загрузка сообщений
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

        # 2. Загрузка отчетов
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
        if self.reports_collection.count() == 0:
            logging.info("Инициализация mock-данных для отчетов...")
            self._populate_collection(self.reports_collection, IDEAL_REPORTS)

        if self.messages_collection.count() == 0:
            logging.info("Инициализация mock-данных для сообщений...")
            self._populate_collection(self.messages_collection, IDEAL_MESSAGES)

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
