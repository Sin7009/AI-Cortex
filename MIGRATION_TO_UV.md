# Миграция на uv

Этот документ описывает процесс миграции с pip/venv на uv для существующих пользователей проекта AI-Cortex.

## Что такое uv?

[uv](https://github.com/astral-sh/uv) - это невероятно быстрый менеджер пакетов Python, написанный на Rust. Он совместим с pip и может работать с существующими `requirements.txt` и `pyproject.toml` файлами.

### Преимущества uv:
- 🚀 **10-100x быстрее** чем pip
- 🔒 Автоматическое создание lock-файла для воспроизводимых сборок
- 📦 Управление виртуальными окружениями из коробки
- 🎯 Полная совместимость с pip
- 💾 Эффективное кэширование пакетов

## Шаги миграции

### 1. Установка uv

#### Linux/macOS:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Windows:
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### Через pip (альтернатива):
```bash
pip install uv
```

### 2. Удаление старого виртуального окружения (опционально)

Если у вас уже есть виртуальное окружение, созданное с помощью venv:

```bash
# Деактивируйте текущее окружение
deactivate

# Удалите старую директорию venv
rm -rf venv/
```

### 3. Установка зависимостей с помощью uv

```bash
cd /path/to/AI-Cortex

# uv автоматически создаст виртуальное окружение в .venv и установит все зависимости
uv sync
```

Эта команда:
- Создаст виртуальное окружение в `.venv/`
- Установит все зависимости из `pyproject.toml`
- Создаст `uv.lock` файл для воспроизводимых сборок

### 4. Запуск проекта

Теперь вы можете запускать проект двумя способами:

#### Вариант A: Используя `uv run` (рекомендуется)
```bash
uv run python main.py
```

#### Вариант B: Активируя виртуальное окружение вручную
```bash
# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

# Запуск проекта
python main.py
```

### 5. Установка опциональных зависимостей

Если вам нужны дополнительные зависимости (например, для GigaChat или HuggingFace):

```bash
# Для GigaChat
uv sync --extra gigachat

# Для HuggingFace
uv sync --extra huggingface

# Все опциональные зависимости
uv sync --all-extras
```

## Команды uv для повседневной работы

### Добавление новых пакетов
```bash
uv add package-name
```

### Удаление пакетов
```bash
uv remove package-name
```

### Обновление зависимостей
```bash
uv sync --upgrade
```

### Запуск команд в виртуальном окружении
```bash
uv run <command>
```

### Просмотр установленных пакетов
```bash
uv pip list
```

## Обновление скриптов и CI/CD

### До (pip):
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### После (uv):
```bash
uv sync
uv run python main.py
```

## Systemd сервис

Если вы используете systemd для автозапуска бота, обновите путь к виртуальному окружению:

### До:
```ini
Environment="PATH=/path/to/AI-Cortex/venv/bin"
ExecStart=/path/to/AI-Cortex/venv/bin/python main.py
```

### После:
```ini
Environment="PATH=/path/to/AI-Cortex/.venv/bin"
ExecStart=/path/to/AI-Cortex/.venv/bin/python main.py
```

## Обратная совместимость

Проект полностью обратно совместим с pip. Если вы не хотите использовать uv, вы можете продолжать использовать pip с файлом `requirements.txt` (который будет сохранен для обратной совместимости).

## Решение проблем

### uv не найден после установки
Добавьте uv в PATH:
```bash
# Linux/macOS
export PATH="$HOME/.cargo/bin:$PATH"

# Или добавьте в ~/.bashrc или ~/.zshrc
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
```

### Проблемы с SSL-сертификатами
Если у вас проблемы с корпоративными прокси:
```bash
uv sync --no-verify-ssl
```

### Конфликты зависимостей
uv автоматически разрешает конфликты. Если возникают проблемы:
```bash
# Очистить кэш
uv cache clean

# Пересоздать lock-файл
rm uv.lock
uv sync
```

## Дополнительные ресурсы

- [Официальная документация uv](https://github.com/astral-sh/uv)
- [uv vs pip: сравнение производительности](https://github.com/astral-sh/uv#benchmarks)
- [Руководство по миграции](https://docs.astral.sh/uv/guides/projects/)
