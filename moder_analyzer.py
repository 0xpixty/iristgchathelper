import re
import json
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
from tqdm import tqdm
from telethon import TelegramClient
from telethon.tl.types import Message

# Конфигурация
config = {
    "api_id": ,
    "api_hash": "",
    "phone_number": "+",
    "mod_chat_id": -,
    "main_chat_id": -,
    "bot_id": 707693258,
    "history_file": "history.json",
    "report_file": "report.txt"
}

client = TelegramClient("moderation_analyzer", config["api_id"], config["api_hash"])

patterns = {
    "mute": re.compile(
        r"(?P<target>[^\n()]+?)?\s*"
        r"(?:\((?:@?(?P<target_username>[^\s)]+)|tg://user\?id=(?P<user_id>\d+)|https://t\.me/(?P<telegram_username>[^\s)]+)|(?P<other>[^\s)]*))\))?\s*"
        r"лишается права слова\s*на\s*(?P<duration>\d+\s*(?:день|дня|дней|час|часа|часов|минут[ы]?))\s*"
        r"(?:💬\s*Причина:\s*(?P<reason>[^\n]+))?",
        re.IGNORECASE
    ),
    "warn": re.compile(
        r"(?P<target>[^\n()]+?)?\s*"
        r"(?:\((?:@?(?P<target_username>[^\s)]+)|tg://user\?id=(?P<user_id>\d+)|https://t\.me/(?P<telegram_username>[^\s)]+)|(?P<other>[^\s)]*))\))?\s*"
        r"получает предупреждение(?:\s*\(\d/3\))?\s*⏱\s*"
        r"Будет снято через\s*(?P<duration>[\d\sа-яa-z]+)\s*"
        r"(?:💬\s*Причина:\s*(?P<reason>[^\n]+))?",
        re.IGNORECASE
    ),
    "ban": re.compile(
        r"(?P<target>[^\n()]+?)?\s*"
        r"(?:\((?:@?(?P<target_username>[^\s)]+)|tg://user\?id=(?P<user_id>\d+)|https://t\.me/(?P<telegram_username>[^\s)]+)|(?P<other>[^\s)]*))\))?\s*"
        r"получает бан\s*(?P<duration>навсегда|\d+[smhdw]?)\s*"
        r"(?:💬\s*Причина:\s*(?P<reason>[^\n]+))?",
        re.IGNORECASE
    ),
    "moderator": re.compile(
        r"(?:👺|🦸|👮‍)\s*Модератор:\s*(?P<name>[^(\n]+)\s*(?:\(@?(?P<username>[^\s)]+)\))?",
        re.IGNORECASE
    )
}

class ModerationAnalyzer:
    def __init__(self):
        self.reset_data()
        self.full_rescan = False

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
                
                print(f"Загружено: {len(self.mutes)} мутов, {len(self.warns)} варнов, {len(self.bans)} банов")
                
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"История не загружена (новый анализ): {e}")
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
            print("История сохранена")
        except Exception as e:
            print(f"Ошибка сохранения истории: {e}")

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
                    target_username = match.group("target_username") if match.group("target_username") else None
                    user_id = match.group("user_id") if match.group("user_id") else None
                    telegram_username = match.group("telegram_username") if match.group("telegram_username") else None
                    other = match.group("other") if match.group("other") else None
                    
                    if not any([target, target_username, user_id, telegram_username]) and other in ["", None]:
                        print(f"Пропущено (пустой target): ID {message.id}, текст: {text}")
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
                    target_username = match.group("target_username") if match.group("target_username") else None
                    user_id = match.group("user_id") if match.group("user_id") else None
                    telegram_username = match.group("telegram_username") if match.group("telegram_username") else None
                    other = match.group("other") if match.group("other") else None
                    
                    if not any([target, target_username, user_id, telegram_username]) and other in ["", None]:
                        print(f"Пропущено (пустой target): ID {message.id}, текст: {text}")
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
                    target_username = match.group("target_username") if match.group("target_username") else None
                    user_id = match.group("user_id") if match.group("user_id") else None
                    telegram_username = match.group("telegram_username") if match.group("telegram_username") else None
                    other = match.group("other") if match.group("other") else None
                    
                    if not any([target, target_username, user_id, telegram_username]) and other in ["", None]:
                        print(f"Пропущено (пустой target): ID {message.id}, текст: {text}")
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
                # Формируем ключ: user_id > target_username > target
                target_key = action["user_id"] or action["target_username"] or action["target"] or f"unknown_{action['id']}"
                if not target_key or target_key.strip() in ["", "⁬"]:
                    print(f"Пропущено (некорректный target_key): ID {message.id}, текст: {text}")
                    return False
                
                self.target_stats[target_key][action_type + "s"] += 1
                self.target_stats[target_key]["moderators"].add(action["moderator"])
                print(f"Найдено действие: {action_type} от {action['moderator']} для {target_key}")
                return True
                
        except Exception as e:
            print(f"Ошибка анализа сообщения {message.id}: {str(e)[:100]}..., текст: {text}")
            
        return False

    async def analyze_all_messages(self):
        try:
            chat = await client.get_entity(config["main_chat_id"])
            bot_entity = await client.get_entity(config["bot_id"])
            
            total = await client.get_messages(chat, limit=0, from_user=bot_entity)
            print(f"Всего сообщений от бота: {total.total}")
            
            async for message in client.iter_messages(
                chat,
                from_user=bot_entity,
                reverse=True,
                limit=None
            ):
                try:
                    await self.analyze_message(message)
                except Exception as e:
                    print(f"Ошибка в сообщении {message.id}: {str(e)[:100]}..., текст: {message.text}")
                    continue
                    
            if self.mutes or self.warns or self.bans:
                self.last_message_id = max(
                    *(m.get('id', 0) for m in self.mutes),
                    *(w.get('id', 0) for w in self.warns),
                    *(b.get('id', 0) for b in self.bans))
            
        except Exception as e:
            print(f"Ошибка анализа: {e}")
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
            print(f"Найдено {len(moderators)} модераторов")
            return moderators
        except Exception as e:
            print(f"Ошибка при получении списка модераторов: {e}")
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

    async def generate_report(self):
        current_date = datetime.now(timezone.utc)
        
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
            print(f"Ошибка при получении списка модераторов: {e}")

        mute_week, mute_month, mute_total = self.get_period_stats(self.mutes, current_date)
        warn_week, warn_month, warn_total = self.get_period_stats(self.warns, current_date)
        ban_week, ban_month, ban_total = self.get_period_stats(self.bans, current_date)
        
        self.mutes.sort(key=lambda x: x["timestamp"])
        self.warns.sort(key=lambda x: x["timestamp"])
        self.bans.sort(key=lambda x: x["timestamp"])
        
        try:
            with open(config["report_file"], "w", encoding="utf-8") as f:
                f.write(f"Отчет о модерации ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n")
                f.write(f"Всего действий: {len(self.mutes)} мутов, {len(self.warns)} варнов, {len(self.bans)} банов\n\n")
                
                # Муты
                f.write("------ Муты ------\n")
                for mute in self.mutes[-10:]:
                    ts = mute["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    target = f"@{mute['target_username']}" if mute['target_username'] else f"tg://user?id={mute['user_id']}" if mute['user_id'] else mute['target'] or f"unknown_{mute['id']}"
                    f.write(f"[{ts}] {mute['moderator']} → {target} ({mute['duration']})")
                    if mute['reason'] != "Не указана":
                        f.write(f" | Причина: {mute['reason']}")
                    f.write("\n")
                
                f.write("\nСтатистика мутов:\n")
                for mod, count in mute_total.most_common():
                    f.write(f"- {mod}: {count}\n")
                
                # Варны
                f.write("\n------ Варны ------\n")
                for warn in self.warns[-10:]:
                    ts = warn["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    target = f"@{warn['target_username']}" if warn['target_username'] else f"tg://user?id={warn['user_id']}" if warn['user_id'] else warn['target'] or f"unknown_{warn['id']}"
                    f.write(f"[{ts}] {warn['moderator']} → {target} ({warn['duration']})")
                    if warn['reason'] != "Не указана":
                        f.write(f" | Причина: {warn['reason']}")
                    f.write("\n")
                
                f.write("\nСтатистика варнов:\n")
                for mod, count in warn_total.most_common():
                    f.write(f"- {mod}: {count}\n")
                
                # Баны
                f.write("\n------ Баны ------\n")
                for ban in self.bans[-10:]:
                    ts = ban["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    target = f"@{ban['target_username']}" if ban['target_username'] else f"tg://user?id={ban['user_id']}" if ban['user_id'] else ban['target'] or f"unknown_{ban['id']}"
                    f.write(f"[{ts}] {ban['moderator']} → {target} ({ban['duration']})")
                    if ban['reason'] != "Не указана":
                        f.write(f" | Причина: {ban['reason']}")
                    f.write("\n")
                
                f.write("\nСтатистика банов:\n")
                for mod, count in ban_total.most_common():
                    f.write(f"- {mod}: {count}\n")
                
                # Топ-5 нарушителей среди пользователей
                f.write("\n------ Топ-5 нарушителей ------\n")

                violators = defaultdict(lambda: {'mutes': 0, 'warns': 0, 'bans': 0})
                for mute in self.mutes:
                    target_key = mute['user_id'] or mute['target_username'] or mute['target'] or f"unknown_{mute['id']}"
                    violators[target_key]['mutes'] += 1
                for warn in self.warns:
                    target_key = warn['user_id'] or warn['target_username'] or warn['target'] or f"unknown_{warn['id']}"
                    violators[target_key]['warns'] += 1
                for ban in self.bans:
                    target_key = ban['user_id'] or ban['target_username'] or ban['target'] or f"unknown_{ban['id']}"
                    violators[target_key]['bans'] += 1

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
                    display_name = f"@{user}" if user.isdigit() or ' ' not in user else user
                    f.write(f"{i}. {display_name}:\n")
                    f.write(f"   Всего нарушений: {total}\n")
                    f.write(f"   • Муты: {stats['mutes']}\n")
                    f.write(f"   • Варны: {stats['warns']}\n")
                    f.write(f"   • Баны: {stats['bans']}\n\n")

                if not sorted_violators:
                    f.write("Нет данных о нарушениях\n\n")
                
                # Топ-5 активных модераторов
                f.write("\n------ Топ-5 активных модераторов ------\n")
                
                mod_activity = defaultdict(lambda: {'mutes': 0, 'warns': 0, 'bans': 0})
                
                for mute in self.mutes:
                    mod_activity[mute['moderator']]['mutes'] += 1
                for warn in self.warns:
                    mod_activity[mute['moderator']]['warns'] += 1
                for ban in self.bans:
                    mod_activity[mute['moderator']]['bans'] += 1

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
                
            print(f"Отчет сохранен в {config['report_file']}")
        except Exception as e:
            print(f"Ошибка генерации отчета: {e}")

async def main():
    analyzer = ModerationAnalyzer()
    analyzer.load_history()
    
    await client.start(config["phone_number"])
    if not await client.is_user_authorized():
        await client.send_code_request(config["phone_number"])
        code = input('Введите код из Telegram: ')
        await client.sign_in(config["phone_number"], code)
    
    try:
        if analyzer.full_rescan:
            print("Запуск полного анализа...")
            await analyzer.analyze_all_messages()
        else:
            print("Анализ новых сообщений...")
            chat = await client.get_entity(config["main_chat_id"])
            bot_entity = await client.get_entity(config["bot_id"])
            
            total = await client.get_messages(chat, limit=0, from_user=bot_entity)
            print(f"Всего сообщений от бота: {total.total}")
            
            async for message in client.iter_messages(
                chat,
                from_user=bot_entity,
                min_id=analyzer.last_message_id + 1,
                reverse=True,
                limit=None
            ):
                try:
                    await analyzer.analyze_message(message)
                except Exception as e:
                    print(f"Ошибка в сообщении {message.id}: {str(e)[:100]}..., текст: {message.text}")
                    continue
        
        analyzer.save_history()
        await analyzer.generate_report()
        
    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
