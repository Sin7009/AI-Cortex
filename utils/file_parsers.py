# -*- coding: utf-8 -*-
import logging
from io import BytesIO
from docx import Document as DocxDocument
from pypdf import PdfReader

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
