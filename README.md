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

🚀 Использование
```bash
python moder_analyzer.py
```

После запуска будет сгенерирован отчет в файле reports/latest_report.txt
📌 Пример отчета

```bash
Отчет о модерации (2023-11-15 14:30:45)

Всего действий: 42 мута, 15 варнов, 3 бана

------ Топ-5 нарушителей ------
1. @User123:
   Всего нарушений: 12
   • Муты: 10
   • Варны: 2

2. @SpammerPro:
   Всего нарушений: 8
   • Муты: 6
   • Варны: 2

------ Топ-5 модераторов ------
1. @BestModerator:
   Всего действий: 28
   • Мутов: 15
   • Варнов: 12
   • Банов: 1
```

| Создано с ❤️ для модераторов Telegram | [zxpixty] | 2025
