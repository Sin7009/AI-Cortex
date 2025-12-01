FROM python:3.11-slim-bookworm

# Установка системных зависимостей (git нужен для некоторых питон-пакетов)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Установка uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Копируем файлы зависимостей
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости в системный Python (так проще в контейнере)
# Флаг --system говорит uv не создавать venv, а ставить прямо в образ
RUN uv pip install --system .

# Копируем код проекта
COPY . .

# Создаем директории для данных
RUN mkdir -p chroma_db knowledge_base

# Команда запуска
CMD ["python", "main.py"]
