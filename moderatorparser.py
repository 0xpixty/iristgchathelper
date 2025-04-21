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
    "history_file": "moderation_history.json",
    "report_file": "moderation_report.txt"
}

client = TelegramClient("moderation_analyzer", config["api_id"], config["api_hash"])

patterns = {
    "mute": re.compile(
        r"(?P<target>[^\n()]+?)\s*\(@?(?P<target_username>[^\s)]+)?\)\s*"
        r"лишается права слова\s*на\s*(?P<duration>\d+\s*(?:день|дня|дней|час|часа|часов|минут[ы]?))\s*"
        r"(?:💬\s*Причина:\s*(?P<reason>[^\n]+))?",
        re.IGNORECASE
    ),
    "warn": re.compile(
        r"(?P<target>[^\n()]+?)\s*\(@?(?P<target_username>[^\s)]+)?\)\s*"
        r"получает предупреждение(?:\s*\(\d/3\))?\s*⏱\s*"
        r"Будет снято через\s*(?P<duration>[\d\sа-яa-z]+)\s*"
        r"(?:💬\s*Причина:\s*(?P<reason>[^\n]+))?",
        re.IGNORECASE
    ),
    "ban": re.compile(
        r"(?P<target>[^\n()]+?)\s*\(@?(?P<target_username>[^\s)]+)?\)\s*"
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
            
        text = message.text
        action = None
        action_type = None
        
        try:
            if "лишается права слова" in text.lower():
                match = patterns["mute"].search(text)
                if match and match.group("target").strip() not in ["", "⁬"]:
                    mod_match = patterns["moderator"].search(text)
                    moderator = mod_match.group("name").strip() if mod_match else "Неизвестный"
                    
                    action = {
                        "timestamp": message.date,
                        "moderator": moderator,
                        "target": match.group("target").strip(),
                        "target_username": match.group("target_username"),
                        "reason": match.group("reason") or "Не указана",
                        "duration": match.group("duration"),
                        "id": message.id
                    }
                    self.mutes.append(action)
                    action_type = "mute"

            elif "получает предупреждение" in text.lower():
                match = patterns["warn"].search(text)
                if match and match.group("target").strip() not in ["", "⁬"]:
                    mod_match = patterns["moderator"].search(text)
                    moderator = mod_match.group("name").strip() if mod_match else "Неизвестный"
                    
                    action = {
                        "timestamp": message.date,
                        "moderator": moderator,
                        "target": match.group("target").strip(),
                        "target_username": match.group("target_username"),
                        "reason": match.group("reason") or "Не указана",
                        "duration": match.group("duration"),
                        "id": message.id
                    }
                    self.warns.append(action)
                    action_type = "warn"

            elif "получает бан" in text.lower():
                match = patterns["ban"].search(text)
                if match and match.group("target").strip() not in ["", "⁬"]:
                    mod_match = patterns["moderator"].search(text)
                    moderator = mod_match.group("name").strip() if mod_match else "Неизвестный"
                    
                    action = {
                        "timestamp": message.date,
                        "moderator": moderator,
                        "target": match.group("target").strip(),
                        "target_username": match.group("target_username"),
                        "reason": match.group("reason") or "Не указана",
                        "duration": match.group("duration"),
                        "id": message.id
                    }
                    self.bans.append(action)
                    action_type = "ban"
            
            if action:
                target_key = action["target_username"] or action["target"]
                self.target_stats[target_key][action_type + "s"] += 1
                self.target_stats[target_key]["moderators"].add(action["moderator"])
                print(f"Найдено действие: {action_type} от {action['moderator']} для {action['target']}")
                return True
                
        except Exception as e:
            print(f"Ошибка анализа сообщения {message.id}: {str(e)[:100]}...")
            
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
                    print(f"Ошибка в сообщении {message.id}: {str(e)[:100]}...")
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

    def generate_report(self):
        current_date = datetime.now(timezone.utc)

        moderators_list = []
        try:
            with client:
                mod_chat = client.loop.run_until_complete(client.get_entity(config["mod_chat_id"]))
                participants = client.loop.run_until_complete(client.get_participants(mod_chat))
                for member in participants:
                    if not member.bot:
                        if member.username:
                            moderators_list.append(f"@{member.username}")
                        moderators_list.append(member.first_name)
        except Exception as e:
            print(f"Ошибка при получении списка модераторов: {e}")
    
        mute_week, mute_month, mute_total = self.get_period_stats(self.mutes, current_date)
        warn_week, warn_month, warn_total = self.get_period_stats(self.warns, current_date)
        ban_week, ban_month, ban_total = self.get_period_stats(self.bans, current_date)
    
        self.mutes.sort(key=lambda x: x["timestamp"])
        self.warns.sort(key=lambda x: x["timestamp"])
        self.bans.sort(key=lambda x: x["timestamp"])
        
        # Генерируем отчет
        try:
            with open(config["report_file"], "w", encoding="utf-8") as f:
                f.write(f"Отчет о модерации ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n")
                f.write(f"Всего действий: {len(self.mutes)} мутов, {len(self.warns)} варнов, {len(self.bans)} банов\n\n")
                
                f.write("------ Муты ------\n")
                for mute in self.mutes[-10:]:
                    ts = mute["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    target = f"@{mute['target_username']}" if mute['target_username'] else mute['target']
                    f.write(f"[{ts}] {mute['moderator']} → {target} ({mute['duration']})")
                    if mute['reason'] != "Не указана":
                        f.write(f" | Причина: {mute['reason']}")
                    f.write("\n")
                
                f.write("\nСтатистика мутов:\n")
                for mod, count in mute_total.most_common():
                    f.write(f"- {mod}: {count}\n")
                
                f.write("\n------ Варны ------\n")
                for warn in self.warns[-10:]:
                    ts = warn["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    target = f"@{warn['target_username']}" if warn['target_username'] else warn['target']
                    f.write(f"[{ts}] {warn['moderator']} → {target} ({warn['duration']})")
                    if warn['reason'] != "Не указана":
                        f.write(f" | Причина: {warn['reason']}")
                    f.write("\n")
                
                f.write("\nСтатистика варнов:\n")
                for mod, count in warn_total.most_common():
                    f.write(f"- {mod}: {count}\n")
                
                f.write("\n------ Баны ------\n")
                for ban in self.bans[-10:]:
                    ts = ban["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    target = f"@{ban['target_username']}" if ban['target_username'] else ban['target']
                    f.write(f"[{ts}] {ban['moderator']} → {target} ({ban['duration']})")
                    if ban['reason'] != "Не указана":
                        f.write(f" | Причина: {ban['reason']}")
                    f.write("\n")
                
                f.write("\nСтатистика банов:\n")
                for mod, count in ban_total.most_common():
                    f.write(f"- {mod}: {count}\n")
                
                # Статистика по пользователям (топ-5)
                f.write("\n------ Топ-5 нарушителей ------\n")
    
                user_violations = defaultdict(lambda: {
                    'mutes': 0,
                    'warns': 0,
                    'bans': 0,
                    'moderators': set()
                })

                for mute in self.mutes:
                    target = mute['target_username'] or mute['target']
                    user_violations[target]['mutes'] += 1
                    user_violations[target]['moderators'].add(mute['moderator'])
                
                for warn in self.warns:
                    target = warn['target_username'] or warn['target']
                    user_violations[target]['warns'] += 1
                    user_violations[target]['moderators'].add(warn['moderator'])
                
                for ban in self.bans:
                    target = ban['target_username'] or ban['target']
                    user_violations[target]['bans'] += 1
                    user_violations[target]['moderators'].add(ban['moderator'])

                top_users = []
                for user, stats in user_violations.items():
                    total = stats['mutes'] + stats['warns'] + stats['bans']
                    top_users.append({
                        'user': user,
                        'total': total,
                        'mutes': stats['mutes'],
                        'warns': stats['warns'],
                        'bans': stats['bans'],
                        'moderators': ', '.join(stats['moderators']) if stats['moderators'] else 'неизвестно'
                    })

                top_users.sort(key=lambda x: x['total'], reverse=True)

                for i, user in enumerate(top_users[:5], 1):
                    display_name = f"@{user['user']}" if not user['user'].startswith(('tg://', 'http')) else user['user']
                    f.write(f"{i}. {display_name}:\n")
                    f.write(f"   Всего нарушений: {user['total']}\n")
                    f.write(f"   • Муты: {user['mutes']}\n")
                    f.write(f"   • Варны: {user['warns']}\n")
                    f.write(f"   • Баны: {user['bans']}\n")
                    f.write(f"   Модераторы: {user['moderators']}\n\n")

                # Статистика по модераторам (топ-5 активных)
                f.write("\n------ Топ-5 модераторов ------\n")
                
                mod_stats = defaultdict(lambda: {'mutes': 0, 'warns': 0, 'bans': 0})
                
                for mute in self.mutes:
                    mod_stats[mute['moderator']]['mutes'] += 1
                for warn in self.warns:
                    mod_stats[warn['moderator']]['warns'] += 1
                for ban in self.bans:
                    mod_stats[ban['moderator']]['bans'] += 1

                moderators = []
                for mod, stats in mod_stats.items():
                    total = stats['mutes'] + stats['warns'] + stats['bans']
                    moderators.append({
                        'name': mod,
                        'total': total,
                        'mutes': stats['mutes'],
                        'warns': stats['warns'],
                        'bans': stats['bans']
                    })

                moderators.sort(key=lambda x: x['total'], reverse=True)
                
                for i, mod in enumerate(moderators[:5], 1):
                    f.write(f"{i}. {mod['name']}:\n")
                    f.write(f"   Всего действий: {mod['total']}\n")
                    f.write(f"   • Выдано мутов: {mod['mutes']}\n")
                    f.write(f"   • Выдано варнов: {mod['warns']}\n")
                    f.write(f"   • Выдано банов: {mod['bans']}\n\n")
            
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
                    print(f"Ошибка в сообщении {message.id}: {str(e)[:100]}...")
                    continue
        
        analyzer.save_history()
        analyzer.generate_report()
        
    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
