# Используем официальный slim образ Python
FROM python:3.11-slim

# Устанавливаем системные зависимости
# curl - для установки uv
# build-essential - для сборки некоторых python пакетов (если потребуется)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем uv для быстрого управления зависимостями
# Копируем бинарник из официального образа — это самый надежный и быстрый способ
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Настройка рабочей директории
WORKDIR /app

# Копируем файлы зависимостей
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости
# --frozen: использовать строго версии из lock-файла
# --no-cache: не кэшировать пакеты, чтобы уменьшить размер образа
# Устанавливаем в системный python (внутри контейнера это ок)
RUN uv sync --frozen --no-cache

# Копируем исходный код проекта
COPY . .

# Создаем директории для данных, если их нет (для volume mount points)
RUN mkdir -p chroma_db knowledge_base

# Указываем команду запуска
# uv run выполнит команду в контексте установленного окружения
CMD ["uv", "run", "python", "main.py"]
