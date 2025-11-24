# Руководство по развертыванию локальной модели на Debian 12

## Обзор

Этот документ содержит пошаговые инструкции по развертыванию собственной локальной модели на виртуальной машине с Debian 12. Мы рассмотрим три варианта:

1. **Ollama** (рекомендуется) - самый простой и быстрый вариант
2. **HuggingFace Transformers** - больше контроля и выбора моделей
3. **vLLM** - для максимальной производительности

---

## Вариант 1: Ollama (Рекомендуется для начала)

### Преимущества Ollama:
- ✅ Простая установка одной командой
- ✅ Автоматическое управление моделями
- ✅ Оптимизированная производительность
- ✅ Поддержка русскоязычных моделей
- ✅ Легкая интеграция с существующим кодом

### Системные требования

**Минимальные:**
- CPU: 4 ядра
- RAM: 8 GB (для моделей 7B)
- Disk: 10 GB свободного места
- OS: Debian 12

**Рекомендуемые:**
- CPU: 8+ ядер
- RAM: 16+ GB (для моделей 13B)
- GPU: NVIDIA с 8+ GB VRAM (опционально, но значительно ускоряет работу)
- Disk: 50+ GB SSD

### Шаг 1: Установка Ollama на Debian 12

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем необходимые зависимости
sudo apt install -y curl git build-essential

# Устанавливаем Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Проверяем установку
ollama --version
```

### Шаг 2: Загрузка русскоязычной модели

Рекомендуемые модели для русского языка:

```bash
# Вариант 1: Llama 3.2 (3B) - быстрая, требует мало ресурсов
ollama pull llama3.2

# Вариант 2: Saiga Llama 3 (8B) - русскоязычная, хорошее качество
# Примечание: модель нужно будет создать через Modelfile (см. ниже)

# Вариант 3: Qwen2.5 (7B) - отличная поддержка русского языка
ollama pull qwen2.5:7b

# Вариант 4: Mistral (7B) - универсальная модель
ollama pull mistral
```

### Шаг 3: (Опционально) Создание Modelfile для Saiga

Если вы хотите использовать специализированную русскоязычную модель Saiga:

```bash
# Создаем директорию для кастомных моделей
mkdir -p ~/ollama-models
cd ~/ollama-models

# Создаем Modelfile
cat > Modelfile << 'EOF'
FROM llama3

PARAMETER temperature 0.7
PARAMETER top_p 0.9

SYSTEM """
Ты — полезный AI-ассистент, специализирующийся на деловой коммуникации на русском языке.
Твоя задача — помогать улучшать отчеты и сообщения для корпоративной переписки.
Отвечай кратко, по делу, используя профессиональный стиль общения.
"""
EOF

# Создаем модель
ollama create saiga-business -f Modelfile
```

### Шаг 4: Настройка Ollama как системного сервиса

```bash
# Ollama уже установлен как systemd сервис
# Проверяем статус
sudo systemctl status ollama

# Включаем автозапуск при загрузке системы
sudo systemctl enable ollama

# Запускаем сервис
sudo systemctl start ollama

# Проверяем, что сервис слушает на порту 11434
curl http://localhost:11434/api/tags
```

### Шаг 5: Настройка удаленного доступа (опционально)

Если вы хотите подключаться к Ollama с других машин:

```bash
# Редактируем systemd unit файл
sudo systemctl edit ollama

# Добавляем следующие строки:
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"

# Сохраняем и перезапускаем
sudo systemctl daemon-reload
sudo systemctl restart ollama

# Настраиваем firewall (если используется)
sudo ufw allow 11434/tcp
```

### Шаг 6: Настройка проекта AI-Cortex

Создайте или отредактируйте файл `.env`:

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Конфигурация модели
MODEL_PROVIDER=ollama
OLLAMA_MODEL=llama3.2  # или другая модель, которую вы загрузили
OLLAMA_BASE_URL=http://localhost:11434  # или IP вашего сервера

# GigaChat API (оставьте для резервного варианта)
# GIGACHAT_API_KEY=your_gigachat_key
```

### Шаг 7: Установка зависимостей проекта

```bash
cd /path/to/AI-Cortex

# Установка uv (если еще не установлен)
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# Установка зависимостей с помощью uv
uv sync

# Запуск бота
uv run python main.py
```

Или активируйте виртуальное окружение вручную:
```bash
source .venv/bin/activate
python main.py
```

### Тестирование

```bash
# Тест 1: Проверяем, что Ollama работает
ollama list  # Должен показать установленные модели

# Тест 2: Проверяем генерацию текста
ollama run llama3.2 "Напиши короткое деловое письмо"

# Тест 3: Проверяем API
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2",
  "prompt": "Привет, как дела?",
  "stream": false
}'
```

---

## Вариант 2: HuggingFace Transformers

### Преимущества:
- Больший выбор моделей
- Полный контроль над параметрами
- Возможность файн-тюнинга

### Недостатки:
- Требует больше технических знаний
- Сложнее в настройке
- Требует GPU для приемлемой скорости

### Установка

```bash
# Устанавливаем CUDA (если есть NVIDIA GPU)
# Инструкции: https://developer.nvidia.com/cuda-downloads

# Устанавливаем зависимости с помощью uv
uv sync --extra huggingface

# Настраиваем .env
MODEL_PROVIDER=huggingface
HUGGINGFACE_MODEL=IlyaGusev/saiga_llama3_8b
```

### Загрузка модели

Модели будут автоматически загружены при первом запуске и закешированы в `~/.cache/huggingface/`

Рекомендуемые русскоязычные модели:
- `IlyaGusev/saiga_llama3_8b` - 8B параметров, хорошее качество
- `IlyaGusev/saiga2_7b` - 7B параметров
- `Qwen/Qwen2.5-7B-Instruct` - отличная модель с поддержкой русского

---

## Вариант 3: vLLM (Для продакшена)

vLLM - это высокопроизводительный inference сервер для LLM моделей.

### Преимущества:
- Максимальная производительность
- Continuous batching
- PagedAttention для эффективного использования памяти

### Установка

```bash
# Требуется Python 3.8-3.11
# Установка vLLM (требуется дополнительная настройка)
uv pip install vllm

# Запуск сервера
python -m vllm.entrypoints.openai.api_server \
  --model IlyaGusev/saiga_llama3_8b \
  --port 8000 \
  --host 0.0.0.0

# В проекте используйте OpenAI-совместимый API
MODEL_PROVIDER=openai
OPENAI_API_BASE=http://localhost:8000/v1
OPENAI_API_KEY=dummy  # vLLM не требует ключ
```

---

## Оптимизация производительности

### 1. Использование квантизации (для экономии памяти)

```bash
# Для Ollama (автоматическая квантизация)
ollama pull llama3.2:7b-q4_K_M  # 4-bit квантизация

# Для HuggingFace (требуется bitsandbytes)
# Модель будет автоматически квантизована при загрузке
```

### 2. Настройка системных параметров

```bash
# Увеличиваем лимиты для процессов
sudo nano /etc/security/limits.conf

# Добавляем:
* soft nofile 65535
* hard nofile 65535

# Настраиваем swap (если мало RAM)
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 3. Мониторинг ресурсов

```bash
# Устанавливаем инструменты мониторинга
sudo apt install -y htop nvtop  # nvtop для GPU

# Мониторим в реальном времени
htop  # CPU и RAM
nvtop  # GPU (если есть)

# Логи Ollama
sudo journalctl -u ollama -f
```

---

## Сравнение вариантов

| Характеристика | Ollama | HuggingFace | vLLM | GigaChat API |
|----------------|--------|-------------|------|--------------|
| Простота установки | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Производительность | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Гибкость | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| Требования к железу | Средние | Высокие | Высокие | Нет |
| Конфиденциальность | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Стоимость | Бесплатно | Бесплатно | Бесплатно | Платно |

---

## Рекомендации по выбору

### Используйте **Ollama**, если:
- ✅ Вы только начинаете с локальными моделями
- ✅ Нужна быстрая настройка
- ✅ Ограниченные ресурсы сервера
- ✅ Хотите простое управление моделями

### Используйте **HuggingFace**, если:
- ✅ Нужен доступ к специфичным моделям
- ✅ Планируете файн-тюнинг
- ✅ Есть мощный GPU
- ✅ Нужен полный контроль над процессом

### Используйте **vLLM**, если:
- ✅ Готовите продакшен-развертывание
- ✅ Нужна максимальная производительность
- ✅ Высокая нагрузка (много одновременных запросов)
- ✅ Есть мощное железо

### Используйте **GigaChat API**, если:
- ✅ Нужна быстрая реализация без своего сервера
- ✅ Непредсказуемая нагрузка
- ✅ Нет требований к конфиденциальности данных
- ✅ Хотите всегда актуальную модель

---

## Решение проблем

### Проблема: Ollama не запускается

```bash
# Проверяем логи
sudo journalctl -u ollama -n 50

# Проверяем порт
sudo netstat -tulpn | grep 11434

# Перезапускаем сервис
sudo systemctl restart ollama
```

### Проблема: Модель работает медленно

```bash
# Используйте квантизованную версию модели
ollama pull llama3.2:7b-q4_K_M

# Уменьшите размер контекстного окна в промптах
# Используйте меньшую модель (3B вместо 7B)
```

### Проблема: Недостаточно памяти

```bash
# Настройте swap
sudo fallocate -l 16G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Используйте более легкую модель
ollama pull llama3.2:3b
```

### Проблема: Ошибка при подключении к Ollama

```bash
# Проверяем, что Ollama запущен
curl http://localhost:11434/api/tags

# Проверяем переменные окружения в .env
cat .env | grep OLLAMA

# Проверяем сетевые настройки
sudo ufw status
```

---

## Автоматизация (Systemd сервис для бота)

Создайте systemd сервис для автоматического запуска бота:

```bash
sudo nano /etc/systemd/system/ai-cortex.service
```

Содержимое файла:

```ini
[Unit]
Description=AI-Cortex Telegram Bot
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/AI-Cortex
Environment="PATH=/path/to/AI-Cortex/.venv/bin"
ExecStart=/path/to/AI-Cortex/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Активация сервиса:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-cortex.service
sudo systemctl start ai-cortex.service

# Проверка статуса
sudo systemctl status ai-cortex.service

# Просмотр логов
sudo journalctl -u ai-cortex.service -f
```

---

## Безопасность

### Рекомендации по безопасности:

1. **Firewall**: Настройте только необходимые порты
```bash
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 11434/tcp  # Только если нужен удаленный доступ к Ollama
```

2. **Обновления**: Регулярно обновляйте систему
```bash
sudo apt update && sudo apt upgrade -y
```

3. **Мониторинг**: Настройте мониторинг логов
```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
```

4. **Бэкапы**: Регулярно делайте резервные копии
```bash
# Бэкап ChromaDB
tar -czf chroma_backup_$(date +%Y%m%d).tar.gz chroma_db/
```

---

## Полезные ссылки

- [Ollama Documentation](https://github.com/ollama/ollama)
- [Ollama Model Library](https://ollama.ai/library)
- [HuggingFace Russian Models](https://huggingface.co/models?language=ru)
- [LangChain Documentation](https://python.langchain.com/docs/get_started/introduction)
- [Saiga Models by IlyaGusev](https://github.com/IlyaGusev/saiga_llama3)
