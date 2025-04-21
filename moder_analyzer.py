import subprocess
import sys
import pkg_resources
import os
from time import sleep
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.prompt import Prompt

# Автоустановка необходимых библиотек
REQUIRED_PACKAGES = ['telethon==1.39.0', 'tqdm==4.67.1', 'rich==13.9.2']

def install_packages():
    console = Console()
    console.print(Panel("Проверка необходимых библиотек...", title="Telegram Moderation Analyzer", border_style="blue"))
    missing = []
    for package in REQUIRED_PACKAGES:
        try:
            pkg_resources.get_distribution(package.split('==')[0])
        except pkg_resources.DistributionNotFound:
            missing.append(package)
    
    if missing:
        console.print(f"Установка библиотек: {', '.join(missing)}", style="yellow")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing)
            console.print("Библиотеки успешно установлены", style="green")
        except subprocess.CalledProcessError as e:
            console.print(f"Ошибка установки библиотек: {e}", style="red")
            sys.exit(1)
    else:
        console.print("Все библиотеки уже установлены", style="green")
    sleep(1)

# Устанавливаем библиотеки при первом запуске
install_packages()

import re
import json
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
from telethon import TelegramClient
from telethon.tl.types import Message

# Конфигурация
config = {
    "api_id": ,
    "api_hash": "",
    "phone_number": "",
    "mod_chat_id": ,
    "main_chat_id": ,
    "bot_id": 707693258,
    "history_file": "history.json",
    "report_file": "report.txt"
}

client = TelegramClient("moderation_analyzer", config["api_id"], config["api_hash"])

patterns = {
    "mute": re.compile(
        r"(?P<target>[^\n()]+?)?\s*"
        r"(?:\((?:@?(?P<target_username>[^\s)]+)|tg://user\?id=(?P<user_id>\d+)|https://t\.me/(?P<telegram_username>[a-zA-Z0-9_]+)|(?P<other>[^\s)]*))\))?\s*"
        r"лишается права слова\s*на\s*(?P<duration>\d+\s*(?:день|дня|дней|час|часа|часов|минут[ы]?))\s*"
        r"(?:💬\s*Причина:\s*(?P<reason>[^\n]+))?",
        re.IGNORECASE
    ),
    "warn": re.compile(
        r"(?P<target>[^\n()]+?)?\s*"
        r"(?:\((?:@?(?P<target_username>[^\s)]+)|tg://user\?id=(?P<user_id>\d+)|https://t\.me/(?P<telegram_username>[a-zA-Z0-9_]+)|(?P<other>[^\s)]*))\))?\s*"
        r"получает предупреждение(?:\s*\(\d/3\))?\s*⏱\s*"
        r"Будет снято через\s*(?P<duration>[\d\sа-яa-z]+)\s*"
        r"(?:💬\s*Причина:\s*(?P<reason>[^\n]+))?",
        re.IGNORECASE
    ),
    "ban": re.compile(
        r"(?P<target>[^\n()]+?)?\s*"
        r"(?:\((?:@?(?P<target_username>[^\s)]+)|tg://user\?id=(?P<user_id>\d+)|https://t\.me/(?P<telegram_username>[a-zA-Z0-9_]+)|(?P<other>[^\s)]*))\))?\s*"
        r"получает бан\s*(?P<duration>навсегда|\d+[smhdw]?)\s*"
        r"(?:💬\s*Причина:\s*(?P<reason>[^\n]+))?",
        re.IGNORECASE
    ),
    "moderator": re.compile(
        r"(?:👺|🦸|👮‍)\s*Модератор:\s*(?P<name>[^(\n]+)\s*(?:\(@?(?P<username>[^\s)]+)\))?",
        re.IGNORECASE
    )
}

def clear_screen():
    sleep(1)
    os.system('cls' if os.name == 'nt' else 'clear')

class ModerationAnalyzer:
    def __init__(self):
        self.reset_data()
        self.full_rescan = False
        self.console = Console()

    def reset_data(self):
        self.mutes = []
        self.warns = []
        self.bans = []
        self.last_message_id = 0
        self.last_analysis = datetime(1970, 1, 1)
        self.target_stats = defaultdict(lambda: {
            "mutes": 0, "warns": 0, "bans": 0, "moderators": set()
        })

    def load_history(self):
        try:
            with open(config["history_file"], "r", encoding="utf-8") as f:
                data = json.load(f)
                for action_type in ["mutes", "warns", "bans"]:
                    for action in data.get(action_type, []):
                        action["timestamp"] = datetime.fromisoformat(action["timestamp"])
                
                self.mutes = data.get("mutes", [])
                self.warns = data.get("warns", [])
                self.bans = data.get("bans", [])
                self.last_message_id = data.get("last_message_id", 0)
                self.last_analysis = datetime.fromisoformat(data.get("last_analysis", "1970-01-01T00:00:00"))
                
                self.console.print(f"Загружено: {len(self.mutes)} мутов, {len(self.warns)} варнов, {len(self.bans)} банов", style="green")
                
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            self.console.print(f"История не загружена (новый анализ): {e}", style="yellow")
            self.reset_data()
            self.full_rescan = True

    def save_history(self):
        data = {
            "mutes": [{**m, "timestamp": m["timestamp"].isoformat()} for m in self.mutes],
            "warns": [{**w, "timestamp": w["timestamp"].isoformat()} for w in self.warns],
            "bans": [{**b, "timestamp": b["timestamp"].isoformat()} for b in self.bans],
            "last_message_id": self.last_message_id,
            "last_analysis": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            with open(config["history_file"], "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.console.print("История сохранена", style="green")
        except Exception as e:
            self.console.print(f"Ошибка сохранения истории: {e}", style="red")

    async def analyze_message(self, message: Message):
        if not message.text or message.id <= self.last_message_id:
            return False
        
        for action_list in [self.mutes, self.warns, self.bans]:
            if any(action.get('id') == message.id for action in action_list):
                return False
            
        text = message.text
        action = None
        action_type = None
        
        try:
            if "лишается права слова" in text.lower():
                match = patterns["mute"].search(text)
                if match:
                    mod_match = patterns["moderator"].search(text)
                    moderator = mod_match.group("name").strip() if mod_match else "Неизвестный"
                    
                    target = match.group("target").strip() if match.group("target") else ""
                    target_username = match.group("target_username")
                    target_username = target_username.lstrip('@') if target_username else None
                    user_id = match.group("user_id") if match.group("user_id") else None
                    telegram_username = match.group("telegram_username") if match.group("telegram_username") else None
                    if telegram_username and ('/' in telegram_username or telegram_username.startswith('c/')):
                        telegram_username = None
                    other = match.group("other") if match.group("other") else None
                    
                    if not any([target.strip(), target_username, user_id, telegram_username]) and other in ["", None]:
                        self.console.print(f"Пропущено (все поля цели пусты): ID {message.id}, текст: {text[:50]}...", style="yellow")
                        return False
                    
                    action = {
                        "timestamp": message.date,
                        "moderator": moderator,
                        "target": target,
                        "target_username": target_username or telegram_username,
                        "user_id": user_id,
                        "reason": match.group("reason") or "Не указана",
                        "duration": match.group("duration"),
                        "id": message.id
                    }
                    self.mutes.append(action)
                    action_type = "mute"

            elif "получает предупреждение" in text.lower():
                match = patterns["warn"].search(text)
                if match:
                    mod_match = patterns["moderator"].search(text)
                    moderator = mod_match.group("name").strip() if mod_match else "Неизвестный"
                    
                    target = match.group("target").strip() if match.group("target") else ""
                    target_username = match.group("target_username")
                    target_username = target_username.lstrip('@') if target_username else None
                    user_id = match.group("user_id") if match.group("user_id") else None
                    telegram_username = match.group("telegram_username") if match.group("telegram_username") else None
                    if telegram_username and ('/' in telegram_username or telegram_username.startswith('c/')):
                        telegram_username = None
                    other = match.group("other") if match.group("other") else None
                    
                    if not any([target.strip(), target_username, user_id, telegram_username]) and other in ["", None]:
                        self.console.print(f"Пропущено (все поля цели пусты): ID {message.id}, текст: {text[:50]}...", style="yellow")
                        return False
                    
                    action = {
                        "timestamp": message.date,
                        "moderator": moderator,
                        "target": target,
                        "target_username": target_username or telegram_username,
                        "user_id": user_id,
                        "reason": match.group("reason") or "Не указана",
                        "duration": match.group("duration"),
                        "id": message.id
                    }
                    self.warns.append(action)
                    action_type = "warn"

            elif "получает бан" in text.lower():
                match = patterns["ban"].search(text)
                if match:
                    mod_match = patterns["moderator"].search(text)
                    moderator = mod_match.group("name").strip() if mod_match else "Неизвестный"
                    
                    target = match.group("target").strip() if match.group("target") else ""
                    target_username = match.group("target_username")
                    target_username = target_username.lstrip('@') if target_username else None
                    user_id = match.group("user_id") if match.group("user_id") else None
                    telegram_username = match.group("telegram_username") if match.group("telegram_username") else None
                    if telegram_username and ('/' in telegram_username or telegram_username.startswith('c/')):
                        telegram_username = None
                    other = match.group("other") if match.group("other") else None
                    
                    if not any([target.strip(), target_username, user_id, telegram_username]) and other in ["", None]:
                        self.console.print(f"Пропущено (все поля цели пусты): ID {message.id}, текст: {text[:50]}...", style="yellow")
                        return False
                    
                    action = {
                        "timestamp": message.date,
                        "moderator": moderator,
                        "target": target,
                        "target_username": target_username or telegram_username,
                        "user_id": user_id,
                        "reason": match.group("reason") or "Не указана",
                        "duration": match.group("duration"),
                        "id": message.id
                    }
                    self.bans.append(action)
                    action_type = "ban"
            
            if action:
                target_key = action["user_id"] or action["target_username"] or action["target"] or f"unknown_{action['id']}"
                if not target_key or target_key.strip() in ["", "⁬"]:
                    self.console.print(f"Пропущено (некорректный target_key): ID {message.id}, текст: {text[:50]}...", style="yellow")
                    return False
                
                self.target_stats[target_key][action_type + "s"] += 1
                self.target_stats[target_key]["moderators"].add(action["moderator"])
                self.console.print(
                    f"Найдено действие: {action_type} от {action['moderator']} для {target_key}",
                    style="green"
                )
                return True
                
        except Exception as e:
            self.console.print(f"Ошибка анализа сообщения {message.id}: {str(e)[:50]}..., текст: {text[:50]}...", style="red")
            
        return False

    async def analyze_all_messages(self):
        try:
            chat = await client.get_entity(config["main_chat_id"])
            bot_entity = await client.get_entity(config["bot_id"])
            
            total = await client.get_messages(chat, limit=0, from_user=bot_entity)
            self.console.print(f"Всего сообщений от бота: {total.total}", style="blue")
            
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                TimeRemainingColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("[cyan]Анализ сообщений...", total=total.total)
                
                async for message in client.iter_messages(
                    chat,
                    from_user=bot_entity,
                    reverse=True,
                    limit=None
                ):
                    try:
                        await self.analyze_message(message)
                        progress.update(task, advance=1)
                    except Exception as e:
                        self.console.print(f"Ошибка в сообщении {message.id}: {str(e)[:50]}...", style="red")
                        continue
                
                progress.update(task, completed=total.total)
            
            if self.mutes or self.warns or self.bans:
                self.last_message_id = max(
                    *(m.get('id', 0) for m in self.mutes),
                    *(w.get('id', 0) for w in self.warns),
                    *(b.get('id', 0) for b in self.bans))
            
        except Exception as e:
            self.console.print(f"Ошибка анализа: {e}", style="red")
            raise

    async def get_moderators(self):
        moderators = []
        try:
            chat = await client.get_entity(config["mod_chat_id"])
            async for member in client.iter_participants(chat):
                if not member.bot:
                    moderators.append({
                        "id": member.id,
                        "name": member.first_name,
                        "username": member.username
                    })
            self.console.print(f"Найдено {len(moderators)} модераторов", style="blue")
            return moderators
        except Exception as e:
            self.console.print(f"Ошибка при получении списка модераторов: {e}", style="red")
            return []

    def get_period_stats(self, actions, current_date):
        week_ago = current_date - timedelta(days=7)
        month_ago = current_date - timedelta(days=30)
        
        week_count = Counter()
        month_count = Counter()
        total_count = Counter()
        
        for action in actions:
            moderator = action["moderator"]
            timestamp = action["timestamp"]
            
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            total_count[moderator] += 1
            if timestamp >= week_ago:
                week_count[moderator] += 1
            if timestamp >= month_ago:
                month_count[moderator] += 1
        
        return week_count, month_count, total_count

    async def generate_report(self, period="all"):
        current_date = datetime.now(timezone.utc)
        
        # Фильтрация действий по периоду
        mutes = self.mutes
        warns = self.warns
        bans = self.bans
        if period == "week":
            week_ago = current_date - timedelta(days=7)
            mutes = [m for m in self.mutes if m["timestamp"] >= week_ago]
            warns = [w for w in self.warns if w["timestamp"] >= week_ago]
            bans = [b for b in self.bans if b["timestamp"] >= week_ago]
        elif period == "month":
            month_ago = current_date - timedelta(days=30)
            mutes = [m for m in self.mutes if m["timestamp"] >= month_ago]
            warns = [w for w in self.warns if w["timestamp"] >= month_ago]
            bans = [b for b in self.bans if b["timestamp"] >= month_ago]
        
        moderators_list = []
        try:
            mod_chat = await client.get_entity(config["mod_chat_id"])
            async for member in client.iter_participants(mod_chat):
                if not member.bot:
                    name_variants = []
                    if member.first_name:
                        name_variants.append(member.first_name)
                    if member.last_name:
                        name_variants.append(f"{member.first_name} {member.last_name}")
                    if member.username:
                        name_variants.append(f"@{member.username}")
                    
                    for name in set(name_variants):
                        if name.strip():
                            moderators_list.append(name.lower())
        except Exception as e:
            self.console.print(f"Ошибка при получении списка модераторов: {e}", style="red")

        mute_week, mute_month, mute_total = self.get_period_stats(mutes, current_date)
        warn_week, warn_month, warn_total = self.get_period_stats(warns, current_date)
        ban_week, ban_month, ban_total = self.get_period_stats(bans, current_date)
        
        mutes.sort(key=lambda x: x["timestamp"])
        warns.sort(key=lambda x: x["timestamp"])
        bans.sort(key=lambda x: x["timestamp"])
        
        period_label = {
            "all": "за всё время",
            "week": "за неделю",
            "month": "за месяц",
            "top": "только топ-5"
        }[period]
        
        try:
            with open(config["report_file"], "w", encoding="utf-8") as f:
                f.write(f"Отчет о модерации ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n")
                f.write(f"Период: {period_label}\n")
                f.write(f"Всего действий: {len(mutes)} мутов, {len(warns)} варнов, {len(bans)} банов\n\n")
                
                if period != "top":
                    f.write("------ Муты ------\n")
                    for mute in mutes[-10:]:
                        ts = mute["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                        target = (f"@{mute['target_username']}" if mute['target_username'] else
                                  f"tg://user?id={mute['user_id']}" if mute['user_id'] else
                                  mute['target'] or f"unknown_{mute['id']}")
                        f.write(f"[{ts}] {mute['moderator']} → {target} ({mute['duration']})")
                        if mute['reason'] != "Не указана":
                            f.write(f" | Причина: {mute['reason']}")
                        f.write("\n")
                    
                    f.write("\nСтатистика мутов:\n")
                    for mod, count in mute_total.most_common():
                        f.write(f"- {mod}: {count}\n")
                    
                    f.write("\n------ Варны ------\n")
                    for warn in warns[-10:]:
                        ts = warn["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                        target = (f"@{warn['target_username']}" if warn['target_username'] else
                                  f"tg://user?id={warn['user_id']}" if warn['user_id'] else
                                  warn['target'] or f"unknown_{warn['id']}")
                        f.write(f"[{ts}] {warn['moderator']} → {target} ({warn['duration']})")
                        if warn['reason'] != "Не указана":
                            f.write(f" | Причина: {warn['reason']}")
                        f.write("\n")
                    
                    f.write("\nСтатистика варнов:\n")
                    for mod, count in warn_total.most_common():
                        f.write(f"- {mod}: {count}\n")
                    
                    f.write("\n------ Баны ------\n")
                    for ban in bans[-10:]:
                        ts = ban["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                        target = (f"@{ban['target_username']}" if ban['target_username'] else
                                  f"tg://user?id={ban['user_id']}" if ban['user_id'] else
                                  ban['target'] or f"unknown_{ban['id']}")
                        f.write(f"[{ts}] {ban['moderator']} → {target} ({ban['duration']})")
                        if ban['reason'] != "Не указана":
                            f.write(f" | Причина: {ban['reason']}")
                        f.write("\n")
                    
                    f.write("\nСтатистика банов:\n")
                    for mod, count in ban_total.most_common():
                        f.write(f"- {mod}: {count}\n")
                
                f.write("\n------ Топ-5 нарушителей ------\n")
                violators = defaultdict(lambda: {'mutes': 0, 'warns': 0, 'bans': 0, 'target_username': None, 'user_id': None})
                for mute in mutes:
                    target_key = mute['user_id'] or mute['target_username'] or mute['target'] or f"unknown_{mute['id']}"
                    violators[target_key]['mutes'] += 1
                    violators[target_key]['target_username'] = mute['target_username'] or violators[target_key]['target_username']
                    violators[target_key]['user_id'] = mute['user_id'] or violators[target_key]['user_id']
                for warn in warns:
                    target_key = warn['user_id'] or warn['target_username'] or warn['target'] or f"unknown_{warn['id']}"
                    violators[target_key]['warns'] += 1
                    violators[target_key]['target_username'] = warn['target_username'] or violators[target_key]['target_username']
                    violators[target_key]['user_id'] = warn['user_id'] or violators[target_key]['user_id']
                for ban in bans:
                    target_key = ban['user_id'] or ban['target_username'] or ban['target'] or f"unknown_{ban['id']}"
                    violators[target_key]['bans'] += 1
                    violators[target_key]['target_username'] = ban['target_username'] or violators[target_key]['target_username']
                    violators[target_key]['user_id'] = ban['user_id'] or violators[target_key]['user_id']

                moderators_exact = set()
                for mod in moderators_list:
                    clean_mod = mod.strip().lower()
                    if clean_mod:
                        moderators_exact.add(clean_mod)

                top_violators = []
                for user, stats in violators.items():
                    clean_user = user.strip().lower()
                    if clean_user not in moderators_exact:
                        top_violators.append((user, stats))

                sorted_violators = sorted(
                    top_violators,
                    key=lambda x: (x[1]['mutes'] + x[1]['warns'] + x[1]['bans']),
                    reverse=True
                )

                for i, (user, stats) in enumerate(sorted_violators[:5], 1):
                    total = stats['mutes'] + stats['warns'] + stats['bans']
                    display_name = (f"@{stats['target_username']}" if stats['target_username'] else
                                    f"tg://user?id={stats['user_id']}" if stats['user_id'] else
                                    user)
                    f.write(f"{i}. {display_name}:\n")
                    f.write(f"   Всего нарушений: {total}\n")
                    f.write(f"   • Муты: {stats['mutes']}\n")
                    f.write(f"   • Варны: {stats['warns']}\n")
                    f.write(f"   • Баны: {stats['bans']}\n\n")

                if not sorted_violators:
                    f.write("Нет данных о нарушениях\n\n")
                
                f.write("\n------ Топ-5 активных модераторов ------\n")
                mod_activity = defaultdict(lambda: {'mutes': 0, 'warns': 0, 'bans': 0})
                for mute in mutes:
                    mod_activity[mute['moderator']]['mutes'] += 1
                for warn in warns:
                    mod_activity[warn['moderator']]['warns'] += 1
                for ban in bans:
                    mod_activity[ban['moderator']]['bans'] += 1

                sorted_mods = sorted(
                    mod_activity.items(),
                    key=lambda x: (x[1]['mutes'] + x[1]['warns'] + x[1]['bans']),
                    reverse=True
                )

                for i, (mod, stats) in enumerate(sorted_mods[:5], 1):
                    total = stats['mutes'] + stats['warns'] + stats['bans']
                    f.write(f"{i}. {mod}:\n")
                    f.write(f"   Всего действий: {total}\n")
                    f.write(f"   • Мутов: {stats['mutes']}\n")
                    f.write(f"   • Варнов: {stats['warns']}\n")
                    f.write(f"   • Банов: {stats['bans']}\n\n")
                
            self.console.print(Panel(
                f"Отчёт сохранён: {config['report_file']}\n"
                f"Период: {period_label}\n"
                f"Результаты:\n"
                f"• Мутов: {len(mutes)}\n"
                f"• Варнов: {len(warns)}\n"
                f"• Банов: {len(bans)}",
                title="Анализ завершён",
                border_style="green"
            ))
        except Exception as e:
            self.console.print(f"Ошибка генерации отчета: {e}", style="red")

async def main():
    analyzer = ModerationAnalyzer()
    console = analyzer.console
    
    clear_screen()
    console.print(Panel(
        "Запуск Telegram Moderation Analyzer\n"
        "Анализирует муты, варны и баны в Telegram-чате с помощью бота Iris\n"
        "Настройте config в moder_analyzer.py перед запуском",
        title="Добро пожаловать",
        border_style="blue"
    ))
    
    analyzer.load_history()
    clear_screen()
    
    await client.start(config["phone_number"])
    if not await client.is_user_authorized():
        console.print("Отправлен код авторизации в Telegram", style="yellow")
        code = Prompt.ask("Введите код из Telegram")
        await client.sign_in(config["phone_number"], code)
    
    user = await client.get_me()
    username = f"@{user.username}" if user.username else f"{user.first_name}"
    console.print(Panel(
        f"Авторизован: {username}\n"
        f"Чат: {config['main_chat_id']}\n"
        f"Бот: {config['bot_id']}",
        title="Авторизация успешна",
        border_style="green"
    ))
    sleep(2)
    clear_screen()
    
    console.print(Panel(
        "Выберите период для анализа:\n"
        "1. Вся статистика\n"
        "2. За неделю\n"
        "3. За месяц\n"
        "4. Только топ-5 нарушителей и модераторов",
        title="Выбор периода",
        border_style="blue"
    ))
    period_choice = Prompt.ask(
        "Введите номер (1-4)",
        choices=["1", "2", "3", "4"],
        default="1"
    )
    period_map = {
        "1": "all",
        "2": "week",
        "3": "month",
        "4": "top"
    }
    period = period_map[period_choice]
    clear_screen()
    
    try:
        if analyzer.full_rescan:
            console.print("Запуск полного анализа...", style="blue")
            await analyzer.analyze_all_messages()
        else:
            console.print("Анализ новых сообщений...", style="blue")
            chat = await client.get_entity(config["main_chat_id"])
            bot_entity = await client.get_entity(config["bot_id"])
            
            total = await client.get_messages(chat, limit=0, from_user=bot_entity)
            console.print(f"Всего сообщений от бота: {total.total}", style="blue")
            
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                TimeRemainingColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Анализ новых сообщений...", total=total.total)
                async for message in client.iter_messages(
                    chat,
                    from_user=bot_entity,
                    min_id=analyzer.last_message_id + 1,
                    reverse=True,
                    limit=None
                ):
                    try:
                        await analyzer.analyze_message(message)
                        progress.update(task, advance=1)
                    except Exception as e:
                        console.print(f"Ошибка в сообщении {message.id}: {str(e)[:50]}...", style="red")
                        continue
        
        analyzer.save_history()
        await analyzer.generate_report(period=period)
        
    except Exception as e:
        console.print(f"Критическая ошибка: {e}", style="red")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
