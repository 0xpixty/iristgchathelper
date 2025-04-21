# 🔍 Telegram Moderation Analyzer

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![Telethon](https://img.shields.io/badge/Telethon-1.25+-green?logo=telegram)
![License](https://img.shields.io/badge/License-MIT-yellow)

Анализатор модерации Telegram-чата с генерацией статистических отчетов. Отслеживает муты, варны и баны, выявляет самых активных нарушителей и модераторов.

## ✨ Особенности

- 📊 Автоматический сбор статистики модерации
- 🔎 Выявление топ-5 нарушителей
- 👮‍♂️ Рейтинг самых активных модераторов
- 📅 Фильтрация по периодам (неделя/месяц)
- 💾 Сохранение истории для последующего анализа
- 📂 Генерация отчетов в удобном формате

## 🛠 Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/0xpixty/tg-moderation-analyzer.git
cd tg-moderation-analyzer
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Настройте конфигурацию в config.py:
```bash
{
    "api_id": 12345,          # Ваш API ID
    "api_hash": "abcdef...",  # Ваш API Hash
    "phone_number": "+123...",# Номер телефона
    "mod_chat_id": -100...,   # ID чата модераторов
    "main_chat_id": -100...,  # ID основного чата
    "bot_id": 123456789,      # ID бота модератора
    "history_file": "data/history.json",
    "report_file": "reports/latest_report.txt"
}
```
