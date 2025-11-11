import os
import json
import random
from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from config import ADMIN_USER_ID

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Розклад"), KeyboardButton(text="📅 Завтра")],
        [KeyboardButton(text="🍲 Меню"), KeyboardButton(text="🧸 Мій Ліцейчик")],
        [KeyboardButton(text="📢 Оголошення")]
    ],
    resize_keyboard=True
)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

AUTHORIZED_LICEYCHYK_FILE = os.path.join(DATA_DIR, "authorized_liceychyk.json")
TAMAGOTCHI_FILE = os.path.join(DATA_DIR, "tamagotchi.json")

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        save_json(path, default)
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

authorized_liceychyk = load_json(AUTHORIZED_LICEYCHYK_FILE, [])
tamagotchi_data = load_json(TAMAGOTCHI_FILE, {})

FOOD_EMOJIS = [
    "🍏", "🍎", "🍐", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🫐", "🍈", "🍒", "🍑", "🥭", "🍍", "🥥", "🥝",
    "🍅", "🍆", "🥑", "🥦", "🥬", "🥒", "🌶️", "🌽", "🥕", "🫒", "🧄", "🧅", "🥔", "🍠", "🥐", "🥯", "🍞",
    "🥖", "🫓", "🥨", "🧀", "🥚", "🍳", "🧈", "🥞", "🧇", "🥓", "🥩", "🍗", "🍖", "🦴", "🌭", "🍔", "🍟",
    "🍕", "🫓", "🥪", "🥙", "🧆", "🌮", "🌯", "🫔", "🥗", "🥘", "🫕", "🥫", "🍝", "🍜", "🍲", "🍛", "🍣",
    "🍱", "🥟", "🦪", "🍤", "🍙", "🍚", "🍘", "🍥", "🥠", "🥮", "🍢", "🍡", "🍧", "🍨", "🍦", "🥧", "🧁",
    "🍰", "🎂", "🍮", "🍭", "🍬", "🍫", "🍿", "🥜", "🌰", "🍯", "🥛", "🫗", "🧃", "🥤", "🧋", "☕", "🍵",
    "🧉", "🍶", "🍺", "🍻", "🥂", "🍷", "🥃", "🍸", "🍹", "🧊", "🫖", "🍾", 
]

DEATH_QUOTES = [
    "Як ви могли??",
    "У вас немає серця...",
    "Я голодний... прощавай...",
    "Навіщо мене створили, якщо не піклуєтеся?",
    "Ви мене вбили...",
    "Я більше не можу...",
    "Самотній і голодний... кінець."
]

liceychyk_router = Router()

GOOD_REPLIES = ["Смачно!", "Дякую!", "Це моє улюблене!", "Обожнюю це!", "Ще давай!"]
BAD_REPLIES = ["Фу!", "Це не смачно...", "Мені не подобається", "Я краще без цього", "Їж це сам!"]
POTION_REPLIES = ["Ого! Енергія!", "Це дивовижно!", "Я відчуваю силу!", "Магія!", "Тепер я супер!"]

def apply_hunger(uid: str):
    data = tamagotchi_data[uid]
    if not data["alive"]:
        return

    last_fed = date.fromisoformat(data["last_fed"])
    today = date.today()
    days_without_food = (today - last_fed).days

    if days_without_food >= 3:
        data["alive"] = False
        data["died_at"] = str(today)
        data["xp"] = 0
        tamagotchi_data[uid] = data
        save_json(TAMAGOTCHI_FILE, tamagotchi_data)

def can_revive(uid: str) -> bool:
    data = tamagotchi_data.get(uid, {})
    if data.get("alive", True):
        return False
    died_at_str = data.get("died_at")
    if not died_at_str:
        return False
    died_at = date.fromisoformat(died_at_str)
    days_since_death = (date.today() - died_at).days
    return days_since_death >= 2

async def show_liceychyk_profile(message: Message, uid: str):
    apply_hunger(uid)

    data = tamagotchi_data[uid]
    xp = data["xp"]
    alive = data["alive"]
    last_fed = data["last_fed"]
    status = "живий" if alive else "мертвий"
    text = f"Ліцейчик\n\nДосвід: {xp}\nСтан: {status}\nОстаннє годування: {last_fed}"

    just_died = not alive and "died_at" in data and data["died_at"] == str(date.today())

    if alive:
        feed_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🍽 Погодувати")]],
            resize_keyboard=True
        )
        await message.answer(text, reply_markup=feed_kb)
    else:
        if "died_at" in data:
            text += f"\nПомер: {data['died_at']}"
        await message.answer(text)

        if just_died:
            await message.answer(f"💔 {random.choice(DEATH_QUOTES)}")

        if can_revive(uid):
            revive_kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="💫 Відродити")]],
                resize_keyboard=True
            )
            await message.answer("Можеш відродити Ліцейчика!", reply_markup=revive_kb)

# === АДМІН-КОМАНДИ ===

@liceychyk_router.message(Command("killliceychyk"))
async def cmd_kill_liceychyk(message: Message):
    if message.from_user.id != ADMIN_USER_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        return
    try:
        user_id = int(parts[1])
    except:
        return
    uid = str(user_id)
    if uid in tamagotchi_data:
        data = tamagotchi_data[uid]
        data["last_fed"] = str(date.today() - timedelta(days=3))
        data["alive"] = True
        tamagotchi_data[uid] = data
        save_json(TAMAGOTCHI_FILE, tamagotchi_data)
        await message.answer("💀 Голод на 3 дні встановлено.")

@liceychyk_router.message(Command("coolliceychyk"))
async def cmd_cooldown_liceychyk(message: Message):
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Вкажіть ID. Приклад:\n/coolliceychyk 123456789")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Невірний ID.")
        return

    uid = str(user_id)
    if uid not in tamagotchi_data:
        await message.answer("У цього користувача немає Ліцейчика.")
        return

    yesterday = str(date.today() - timedelta(days=1))
    data = tamagotchi_data[uid]
    data["last_fed"] = yesterday
    data["last_quiz"] = None
    data["last_daily"] = yesterday
    tamagotchi_data[uid] = data
    save_json(TAMAGOTCHI_FILE, tamagotchi_data)
    await message.answer(f"✅ Кулдауни для {user_id} скинуто.")

@liceychyk_router.message(Command("deleteliceychyk"))
async def cmd_delete_liceychyk(message: Message):
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("❌ У вас немає прав.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Вкажіть ID. Приклад:\n/deleteliceychyk 123456789")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Невірний ID.")
        return

    uid = str(user_id)
    if uid not in tamagotchi_data:
        await message.answer("У цього користувача немає Ліцейчика.")
        return

    del tamagotchi_data[uid]
    save_json(TAMAGOTCHI_FILE, tamagotchi_data)
    await message.answer(f"🗑 Ліцейчик для {user_id} видалено.")

@liceychyk_router.message(Command("addliceychyk"))
async def cmd_add_liceychyk(message: Message):
    if message.from_user.id != ADMIN_USER_ID:
        await message.answer("❌ У вас немає прав для цієї команди.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Вкажіть ID користувача. Приклад:\n/addliceychyk 123456789")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Невірний ID.")
        return
    if user_id not in authorized_liceychyk:
        authorized_liceychyk.append(user_id)
        save_json(AUTHORIZED_LICEYCHYK_FILE, authorized_liceychyk)
        await message.answer("✅ Користувача дозволено мати Ліцейчика.")
    else:
        await message.answer("🔹 Цей користувач уже авторизований.")

def get_feed_keyboard():
    choices = random.sample(FOOD_EMOJIS, 4)
    if random.random() < 0.1:
        idx = random.randint(0, 3)
        choices[idx] = "🧪"
    buttons = [KeyboardButton(text=food) for food in choices]
    return ReplyKeyboardMarkup(keyboard=[buttons], resize_keyboard=True, one_time_keyboard=True)

@liceychyk_router.message(F.text == "🧸 Мій Ліцейчик")
async def show_liceychyk(message: Message):
    user_id = message.from_user.id
    if user_id not in authorized_liceychyk:
        await message.answer("❌ Лише авторизовані учні можуть завести Ліцейчика.")
        return

    uid = str(user_id)
    if uid not in tamagotchi_data:
        tamagotchi_data[uid] = {
            "xp": 100,
            "alive": True,
            "last_fed": str(date.today()),
            "last_quiz": None,
            "last_daily": str(date.today())
        }
        save_json(TAMAGOTCHI_FILE, tamagotchi_data)
        await message.answer("🐣 Вітаю! Твій Ліцейчик народився!\n\nДосвід: 100\nСтан: живий\nОстаннє годування: сьогодні")
        return

    await show_liceychyk_profile(message, uid)

@liceychyk_router.message(F.text == "🍽 Погодувати")
async def feed_liceychyk_start(message: Message):
    user_id = message.from_user.id
    uid = str(user_id)

    if uid not in tamagotchi_data:
        await message.answer("Спочатку заведи Ліцейчика!")
        return

    data = tamagotchi_data[uid]
    if not data["alive"]:
        await message.answer("Ліцейчик мертвий... Спочатку відроди його.")
        return

    if data["last_fed"] == str(date.today()):
        await message.answer("Вже годував сьогодні! Завтра знову можна.")
        return

    await message.answer("Чим погодувати Ліцейчика?", reply_markup=get_feed_keyboard())

@liceychyk_router.message(F.text.in_([*FOOD_EMOJIS, "🧪"]))
async def feed_liceychyk_choice(message: Message):
    user_id = message.from_user.id
    uid = str(user_id)
    chosen = message.text

    if uid not in tamagotchi_data:
        await message.answer("Спочатку заведи Ліцейчика!", reply_markup=main_kb)
        return

    data = tamagotchi_data[uid]
    if not data["alive"]:
        await message.answer("Ліцейчик мертвий... Спочатку відроди його.", reply_markup=main_kb)
        return

    if data["last_fed"] == str(date.today()):
        await message.answer("Вже годував сьогодні!", reply_markup=main_kb)
        return

    if chosen == "🧪":
        data["xp"] += 15
        reply = random.choice(POTION_REPLIES) + " (+15 досвіду)"
    elif chosen in FOOD_EMOJIS:
        if random.random() < 0.2:
            data["xp"] -= 5
            reply = random.choice(BAD_REPLIES) + " (-5 досвіду)"
        else:
            reply = random.choice(GOOD_REPLIES)
    else:
        await message.answer("Невідома їжа.", reply_markup=main_kb)
        return

    if data["xp"] <= 0:
        data["xp"] = 0
        data["alive"] = False
        data["died_at"] = str(date.today())

    data["last_fed"] = str(date.today())
    tamagotchi_data[uid] = data
    save_json(TAMAGOTCHI_FILE, tamagotchi_data)

    await message.answer(f"Ліцейчик: {reply}", reply_markup=main_kb)

@liceychyk_router.message(F.text == "💫 Відродити")
async def revive_liceychyk(message: Message):
    user_id = message.from_user.id
    uid = str(user_id)

    if uid not in tamagotchi_data:
        await message.answer("Спочатку заведи Ліцейчика!")
        return

    data = tamagotchi_data[uid]
    if data.get("alive", False):
        await message.answer("Ліцейчик уже живий!")
        return

    if not can_revive(uid):
        await message.answer("Ще не час відроджувати... Почекай ще трохи.")
        return

    tamagotchi_data[uid] = {
        "xp": 100,
        "alive": True,
        "last_fed": str(date.today()),
        "last_quiz": None,
        "last_daily": str(date.today())
    }
    save_json(TAMAGOTCHI_FILE, tamagotchi_data)
    await message.answer("✨ Ліцейчик відродився! Тепер він знову з тобою.")
    await show_liceychyk_profile(message, uid)