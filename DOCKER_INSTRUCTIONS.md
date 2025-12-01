# Docker Instructions for AI-Cortex (OpenRouter + Local Embeddings)

Этот документ описывает процесс запуска бота AI-Cortex в оптимизированном режиме для серверов с ограниченными ресурсами (4GB RAM).

## Архитектура
- **LLM:** OpenRouter (облачная модель, например `google/gemma-2-9b-it:free`)
- **Эмбеддинги:** Локальные (`intfloat/multilingual-e5-small`)
- **База данных:** ChromaDB (локально в контейнере)

## Предварительные требования

1.  **Docker** и **Docker Compose**.
2.  Файл `.env` с ключом OpenRouter.

## Настройка

1.  **Подготовьте `.env` файл:**
    Убедитесь, что у вас есть ключ от [OpenRouter](https://openrouter.ai/).

    ```env
    TELEGRAM_BOT_TOKEN=ваш_токен
    BOT_PASSWORD=ваш_секретный_пароль
    MODEL_PROVIDER=openrouter
    OPENROUTER_API_KEY=sk-or-...
    OPENROUTER_MODEL=google/gemma-2-9b-it:free
    ```
    > **Важно:** Переменная `BOT_PASSWORD` защищает бота от несанкционированного доступа. По умолчанию используется пароль `secret123`.

2.  **Остановите Ollama (если запущена):**
    Чтобы освободить память для бота:
    ```bash
    sudo systemctl stop ollama
    sudo systemctl disable ollama
    ```

## Запуск

1.  **Соберите и запустите контейнер:**
    ```bash
    docker compose up -d --build
    ```

2.  **Проверка работы:**
    ```bash
    docker compose logs -f
    ```
    Вы должны увидеть: `✅ OpenRouter провайдер готов...`.

## Управление

- **Остановить:** `docker compose down`
- **Перезапустить:** `docker compose restart`
- **Обновить:** `git pull && docker compose up -d --build`

## Данные
Векторная база данных сохраняется в Docker volume `chroma_data`, поэтому "память" бота сохраняется между перезапусками.
