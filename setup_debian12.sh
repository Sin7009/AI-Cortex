#!/bin/bash
# Скрипт быстрой установки Ollama и настройки проекта на Debian 12
# Использование: bash setup_debian12.sh

set -e  # Останавливаем скрипт при ошибке

echo "=========================================="
echo "  AI-Cortex: Установка на Debian 12"
echo "=========================================="
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Проверка, что запущен на Debian
if [ ! -f /etc/debian_version ]; then
    echo -e "${RED}❌ Этот скрипт предназначен для Debian!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Обнаружена система Debian $(cat /etc/debian_version)${NC}"
echo ""

# Обновление системы
echo "📦 Обновление системных пакетов..."
sudo apt update && sudo apt upgrade -y

# Установка необходимых пакетов
echo "📦 Установка зависимостей..."
sudo apt install -y curl git build-essential python3 python3-pip

# Установка Ollama
echo "🚀 Установка Ollama..."
if command -v ollama &> /dev/null; then
    echo -e "${YELLOW}⚠ Ollama уже установлен${NC}"
else
    curl -fsSL https://ollama.ai/install.sh | sh
    echo -e "${GREEN}✓ Ollama успешно установлен${NC}"
fi

# Проверка версии Ollama
echo ""
echo "Версия Ollama:"
ollama --version

# Запуск Ollama сервиса
echo ""
echo "🔧 Настройка Ollama как системного сервиса..."
sudo systemctl enable ollama
sudo systemctl start ollama

# Ожидание запуска сервиса
sleep 3

# Проверка статуса
if systemctl is-active --quiet ollama; then
    echo -e "${GREEN}✓ Ollama сервис запущен${NC}"
else
    echo -e "${RED}❌ Ошибка запуска Ollama сервиса${NC}"
    exit 1
fi

# Выбор модели для загрузки
echo ""
echo "📥 Выберите модель для загрузки:"
echo "1) llama3.2 (3B) - Легкая, быстрая (рекомендуется для начала)"
echo "2) qwen2.5:7b - Отличная поддержка русского языка"
echo "3) mistral - Универсальная модель"
echo "4) Пропустить загрузку модели"
echo ""
read -p "Ваш выбор (1-4): " model_choice

case $model_choice in
    1)
        MODEL_NAME="llama3.2"
        echo "📥 Загрузка модели llama3.2..."
        ollama pull llama3.2
        ;;
    2)
        MODEL_NAME="qwen2.5:7b"
        echo "📥 Загрузка модели qwen2.5:7b (это может занять несколько минут)..."
        ollama pull qwen2.5:7b
        ;;
    3)
        MODEL_NAME="mistral"
        echo "📥 Загрузка модели mistral..."
        ollama pull mistral
        ;;
    4)
        MODEL_NAME="llama3.2"
        echo -e "${YELLOW}⚠ Пропущена загрузка модели. Вы можете загрузить её позже: ollama pull llama3.2${NC}"
        ;;
    *)
        MODEL_NAME="llama3.2"
        echo -e "${YELLOW}⚠ Неверный выбор. Используется llama3.2 по умолчанию${NC}"
        ollama pull llama3.2
        ;;
esac

# Проверка загруженных моделей
echo ""
echo "📋 Установленные модели:"
ollama list

# Установка uv
echo ""
echo "📦 Установка uv (быстрого менеджера пакетов Python)..."
if command -v uv &> /dev/null; then
    echo -e "${YELLOW}⚠ uv уже установлен${NC}"
else
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Добавляем uv в PATH для текущей сессии
    export PATH="$HOME/.cargo/bin:$PATH"
    echo -e "${GREEN}✓ uv успешно установлен${NC}"
fi

# Проверка версии uv
echo ""
echo "Версия uv:"
uv --version

# Настройка проекта AI-Cortex
echo ""
echo "🔧 Настройка проекта AI-Cortex..."

# Установка зависимостей Python с помощью uv
echo "📦 Установка зависимостей Python с помощью uv..."
uv sync

# Создание .env файла, если его нет
if [ ! -f ".env" ]; then
    echo ""
    echo "📝 Настройка файла .env..."
    read -p "Введите ваш Telegram Bot Token: " telegram_token
    
    cat > .env << EOF
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=$telegram_token

# Model Provider Configuration
MODEL_PROVIDER=ollama
OLLAMA_MODEL=$MODEL_NAME
OLLAMA_BASE_URL=http://localhost:11434

# Optional: GigaChat API (для резервного варианта)
# GIGACHAT_API_KEY=your_gigachat_key
EOF
    
    echo -e "${GREEN}✓ Файл .env создан${NC}"
else
    echo -e "${YELLOW}⚠ Файл .env уже существует. Пропускаю создание.${NC}"
    echo "  Для использования Ollama убедитесь, что в .env установлено:"
    echo "  MODEL_PROVIDER=ollama"
    echo "  OLLAMA_MODEL=$MODEL_NAME"
fi

# Тестирование
echo ""
echo "🧪 Тестирование установки..."
echo "  Проверка Ollama API..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo -e "${GREEN}✓ Ollama API работает${NC}"
else
    echo -e "${RED}❌ Ошибка подключения к Ollama API${NC}"
fi

# Создание systemd сервиса для бота (опционально)
echo ""
read -p "Хотите создать systemd сервис для автозапуска бота? (y/n): " create_service

if [ "$create_service" = "y" ] || [ "$create_service" = "Y" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    USER_NAME=$(whoami)
    
    sudo tee /etc/systemd/system/ai-cortex.service > /dev/null << EOF
[Unit]
Description=AI-Cortex Telegram Bot
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$SCRIPT_DIR
Environment="PATH=$SCRIPT_DIR/.venv/bin"
ExecStart=$SCRIPT_DIR/.venv/bin/python $SCRIPT_DIR/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable ai-cortex.service
    
    echo -e "${GREEN}✓ Systemd сервис создан${NC}"
    echo "  Запуск: sudo systemctl start ai-cortex.service"
    echo "  Статус: sudo systemctl status ai-cortex.service"
    echo "  Логи: sudo journalctl -u ai-cortex.service -f"
fi

# Финальные инструкции
echo ""
echo "=========================================="
echo -e "${GREEN}✅ Установка завершена!${NC}"
echo "=========================================="
echo ""
echo "📋 Следующие шаги:"
echo ""
echo "1. Проверьте настройки в файле .env"
echo "   nano .env"
echo ""
echo "2. Запустите бота:"
echo "   uv run python main.py"
echo ""
echo "   Или активируйте виртуальное окружение:"
echo "   source .venv/bin/activate"
echo "   python main.py"
echo ""
if [ "$create_service" = "y" ] || [ "$create_service" = "Y" ]; then
    echo "   Или через systemd:"
    echo "   sudo systemctl start ai-cortex.service"
    echo ""
fi
echo "3. Мониторинг ресурсов:"
echo "   htop  # CPU и RAM"
echo "   sudo journalctl -u ollama -f  # Логи Ollama"
echo ""
echo "4. Управление моделями Ollama:"
echo "   ollama list  # Список установленных моделей"
echo "   ollama pull <model>  # Загрузить новую модель"
echo "   ollama rm <model>  # Удалить модель"
echo ""
echo "📚 Документация: см. DEPLOYMENT.md для подробностей"
echo ""
echo -e "${YELLOW}💡 Совет:${NC} Используйте 'screen' или 'tmux' для запуска бота в фоне:"
echo "   screen -S ai-cortex"
echo "   python main.py"
echo "   # Нажмите Ctrl+A, затем D для отключения от сессии"
echo ""
