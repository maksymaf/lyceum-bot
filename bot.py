import os
import json
from datetime import date, timedelta
from aiogram import Bot, Dispatcher, Router
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from config import TOKEN, ADMIN_USER_ID
from middleware import ThrottlingMiddleware
from aiogram.fsm.storage.redis import RedisStorage
from liceychyk import liceychyk_router
import logging
logging.basicConfig(level=logging.INFO)

DATA_DIR = "data"
SCHEDULE_FILE = os.path.join(DATA_DIR, "schedule.json")
MENU_FILE = os.path.join(DATA_DIR, "menu.json")
ANNOUNCEMENTS_FILE = os.path.join(DATA_DIR, "announcements.json")
HELPERS_FILE = os.path.join(DATA_DIR, "helpers.json")
SUBSCRIBERS_FILE = os.path.join(DATA_DIR, "subscribers.json")

category_names = {
    "general": "📢 Загальне оголошення",
    "events": "📅 Подія",
    "achievements": "🏆 Досягнення"
}

os.makedirs(DATA_DIR, exist_ok=True)

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
        
schedule_data = load_json(SCHEDULE_FILE, {})
menu_data = load_json(MENU_FILE, {})
announcements = load_json(ANNOUNCEMENTS_FILE, [])
helpers = load_json(HELPERS_FILE, [])
subscribers = load_json(SUBSCRIBERS_FILE, [])
classes_list = sorted(schedule_data.keys())

WEEKDAY_NAMES = ["понеділок", "вівторок", "середа", "четвер", "п’ятниця"]
LESSON_TIMES = [
    "8:00–8:45", "9:00–9:45", "10:00–10:45", "11:00–11:45",
    "12:00–12:45", "13:00–13:45", "13:50–14:35", "14:50–15:35"
]

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

pending_announcements = {}

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Розклад"), KeyboardButton(text="📅 Завтра")],
        [KeyboardButton(text="🍲 Меню"), KeyboardButton(text="🧸 Мій Ліцейчик")],
        [KeyboardButton(text="📢 Оголошення")]
    ],
    resize_keyboard=True
)
announcements_inline_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📅 Заходи ліцею", callback_data="ann_events")],
    [InlineKeyboardButton(text="🏆 Досягнення учнів", callback_data="ann_achievements")],
    [InlineKeyboardButton(text="📢 Загальні оголошення", callback_data="ann_general")],
])

def make_rows(items, suffix=""):
    rows = []
    row = []
    for i, item in enumerate(items):
        label = f"{item}{suffix}"
        row.append(KeyboardButton(text=label))
        if (i + 1) % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows

class_buttons_today = make_rows(classes_list, suffix="")
class_buttons_tomorrow = make_rows(classes_list, suffix=" (завтра)")

classes_kb_today = ReplyKeyboardMarkup(keyboard=class_buttons_today, resize_keyboard=True, one_time_keyboard=True)
classes_kb_tomorrow = ReplyKeyboardMarkup(keyboard=class_buttons_tomorrow, resize_keyboard=True, one_time_keyboard=True)

async def show_schedule_for_class(message: Message, class_key: str, tomorrow=False):
    today = date.today()
    target_date = today + timedelta(days=1) if tomorrow else today
    weekday = target_date.weekday()

    if weekday > 4:  # 5 = субота, 6 = неділя
        text = "Завтра вихідний! Розкладу немає." if tomorrow else "Сьогодні вихідний! Розкладу немає."
        await message.answer(text)
        return

    lessons = schedule_data.get(class_key, {}).get(str(weekday), [])
    if not lessons:
        day_name = WEEKDAY_NAMES[weekday].capitalize()
        prefix = "Завтра" if tomorrow else "Сьогодні"
        await message.answer(f"{prefix} ({day_name.lower()}) у класу {class_key} немає уроків.")
        return

    day_name = WEEKDAY_NAMES[weekday].capitalize()
    date_str = target_date.strftime("%d.%m.%Y")
    prefix = "завтра" if tomorrow else "сьогодні"
    text = f"📅 Розклад для {class_key} на {day_name} ({date_str}):\n\n"
    for i, subject in enumerate(lessons):
        time_slot = LESSON_TIMES[i] if i < len(LESSON_TIMES) else "???"
        text += f"{i+1}. {time_slot} — {subject.strip()}\n"

    await message.answer(text, reply_markup=main_kb)

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    if user_id not in subscribers:
        subscribers.append(user_id)
        save_json(SUBSCRIBERS_FILE, subscribers)
    await message.answer("👋 Вітаю у шкільному боті!", reply_markup=main_kb)

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    today_weekday = date.today().weekday()
    if today_weekday > 4:
        await message.answer("Сьогодні вихідний — меню немає.")
        return
    menu = menu_data.get(str(today_weekday))
    await message.answer(menu or "Меню на сьогодні ще не додано.")

@router.message(Command("addhelper"))
async def cmd_add_helper(message: Message):
    if message.from_user.id not in ADMIN_USER_ID:
        await message.answer("❌ У вас немає прав для цієї команди.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Вкажіть ID користувача. Приклад:\n/addhelper 123456789")
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Невірний ID.")
        return
    if user_id not in helpers:
        helpers.append(user_id)
        save_json(HELPERS_FILE, helpers)
        await message.answer("✅ Користувача додано до помічників.")
    else:
        await message.answer("🔹 Цей користувач уже є помічником.")

def get_ann_kb(ann_type: str, index: int, total: int, user_id: int):
    if ann_type != "general" or total <= 1:
        nav = []
    else:
        nav = []
        if index > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"ann_prev_{ann_type}_{index-1}"))
        if index < total - 1:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"ann_next_{ann_type}_{index+1}"))

    kb = []
    if nav:
        kb.append(nav)

    if is_admin_or_helper(user_id):
        kb.append([InlineKeyboardButton(text="🗑 Видалити", callback_data=f"ann_del_{ann_type}_{index}")])

    return InlineKeyboardMarkup(inline_keyboard=kb) if kb else None

def is_admin_or_helper(user_id: int) -> bool:
    return (user_id in ADMIN_USER_ID) or (user_id in helpers)

pending_announcements = {}  # user_id → {"type": "...", "text": "..."}

@router.message(Command("announce"))
async def cmd_announce(message: Message):
    if not is_admin_or_helper(message.from_user.id):
        await message.answer("❌ У вас немає прав для цієї команди.")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "Використання:\n/announce <категорія> <текст>\n"
            "Категорії: general, events, achievements"
        )
        return

    category, text = parts[1], parts[2].strip()
    if category not in ("general", "events", "achievements"):
        await message.answer("Невідома категорія. Використовуйте: general, events, achievements")
        return
    if not text:
        await message.answer("Порожнє оголошення неможливе.")
        return

    pending_announcements[message.from_user.id] = {"type": category, "text": text}
    preview = f"Підтвердіть публікацію:\n\n{category_names[category]}\n\n{text}"

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Підтвердити", callback_data="ann_confirm"),
            InlineKeyboardButton(text="❌ Скасувати", callback_data="ann_cancel")
        ]
    ])

    await message.answer(preview, reply_markup=confirm_kb)

@router.callback_query(lambda c: c.data in ["ann_confirm", "ann_cancel"])
async def handle_announce_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    action = callback.data
    announcement = pending_announcements.get(user_id)
    if not announcement:
        await callback.answer("Немає очікуючого оголошення.", show_alert=True)
        try:
            await callback.message.edit_text("❌ Дія застаріла.")
        except:
            pass
        return

    if action == "ann_cancel":
        pending_announcements.pop(user_id, None)
        try:
            await callback.message.edit_text("❌ Публікацію скасовано.")
        except:
            pass
        await callback.answer()
        return

    category = announcement["type"]
    text = announcement["text"]
    pending_announcements.pop(user_id, None)

    if category == "general":
        announcements.append({"type": "general", "text": text})
        save_json(ANNOUNCEMENTS_FILE, announcements)

        sent_count = 0
        for sub_id in subscribers:
            try:
                await callback.bot.send_message(sub_id, f"📢 {text}")
                sent_count += 1
            except Exception as e:
                logging.warning(f"Не вдалося надіслати {sub_id}: {e}")

        await callback.message.edit_text(f"✅ Оголошення надіслано {sent_count} користувачам і збережено.")
    else:
        if category == "events":
            data_file = "data/events.json"
        else:
            data_file = "data/achievements.json"

        items = load_json(data_file, [])
        items.append(text)
        save_json(data_file, items)
        await callback.message.edit_text(f"✅ {category_names[category]} додано (без розсилки).")

    await callback.answer()

@router.message(lambda m: m.text == "📢 Оголошення")
async def cmd_announcements(message: Message):
    await message.answer("Оберіть категорію оголошень:", reply_markup=announcements_inline_kb)

@router.callback_query(lambda c: c.data and c.data.startswith("ann_"))
async def handle_announcement_callbacks(callback: CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id
    global announcements

    if data == "ann_general":
        general_anns = [a for a in announcements if a["type"] == "general"]
        if not general_anns:
            await callback.message.edit_text("📢 Немає загальних оголошень.")
        else:
            index = len(general_anns) - 1  
            text = f"📢 {general_anns[index]['text']}"
            kb = get_ann_kb("general", index, len(general_anns), user_id)
            await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return

    if data == "ann_events":
        events = load_json("data/events.json", [])
        if not events:
            await callback.message.edit_text("📅 Немає запланованих заходів.")
        else:
            text = "📅 Заходи ліцею:\n\n" + "\n".join(f"- {e}" for e in events)
            await callback.message.edit_text(text)
        await callback.answer()
        return

    if data == "ann_achievements":
        achievements = load_json("data/achievements.json", [])
        if not achievements:
            await callback.message.edit_text("🏆 Немає досягнень учнів.")
        else:
            text = "🏆 Досягнення учнів:\n\n" + "\n".join(f"- {a}" for a in achievements)
            await callback.message.edit_text(text)
        await callback.answer()
        return

    if data == "ann_back":
        await callback.message.edit_text("Повертаю головне меню 👇", reply_markup=main_kb)
        await callback.answer()
        return

    parts = data.split("_")
    if len(parts) < 3:
        await callback.answer()
        return

    action, ann_type, index_str = parts[1], parts[2], parts[3]
    try:
        index = int(index_str)
    except:
        await callback.answer("Помилка індексу.")
        return

    general_anns = [a for a in announcements if a["type"] == "general"]
    if not (0 <= index < len(general_anns)):
        await callback.answer("Оголошення не знайдено.")
        return

    if action == "next" or action == "prev":
        new_index = index + (1 if action == "next" else -1)
        if 0 <= new_index < len(general_anns):
            text = f"📢 {general_anns[new_index]['text']}"
            kb = get_ann_kb("general", new_index, len(general_anns), user_id)
            await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return

    if action == "del":
        if not is_admin_or_helper(user_id):
            await callback.answer("❌ Немає прав.", show_alert=True)
            return
        deleted = general_anns.pop(index)
        
        announcements = [a for a in announcements if not (a["type"] == "general" and a["text"] == deleted["text"])]
        save_json(ANNOUNCEMENTS_FILE, announcements)

        if general_anns:
            new_index = min(index, len(general_anns) - 1)
            text = f"📢 {general_anns[new_index]['text']}"
            kb = get_ann_kb("general", new_index, len(general_anns), user_id)
            await callback.message.edit_text(text, reply_markup=kb)
        else:
            await callback.message.edit_text("📢 Загальних оголошень немає.")
        await callback.answer("Видалено ✅")
        return

    if data == "ann_achievements":
        achievements = load_json("data/achievements.json", [])
        if not achievements:
            await callback.message.edit_text("🏆 Немає досягнень учнів.")
        else:
            text = "🏆 Досягнення учнів:\n\n" + "\n".join(f"- {a}" for a in achievements)
            await callback.message.edit_text(text)
        await callback.answer()
        return

@router.message()
async def handle_text(message: Message):
    text = (message.text or "").strip()
    if text == "📅 Розклад":
        if not schedule_data:
            await message.answer("Розклад ще не додано.")
            return
        await message.answer("Оберіть клас (для сьогодні):", reply_markup=classes_kb_today)
        return
    if text == "📅 Завтра":
        if not schedule_data:
            await message.answer("Розклад ще не додано.")
            return
        await message.answer("Оберіть клас (для завтрашнього дня):", reply_markup=classes_kb_tomorrow)
        return
    if text == "🍲 Меню":
        await cmd_menu(message)
        return
    if text == "📢 Оголошення":
        await cmd_announcements(message)
        return
    if text == "❌ Назад":
        await message.answer("Повертаю головне меню 👇", reply_markup=main_kb)
        return
    if text in schedule_data:
        await show_schedule_for_class(message, text, tomorrow=False)
        return
    if text.endswith(" (завтра)"):
        class_key = text.rsplit(" (завтра)", 1)[0]
        if class_key in schedule_data:
            await show_schedule_for_class(message, class_key, tomorrow=True)
            return
    await message.answer("Не розумію. Скористайтеся кнопками 👇", reply_markup=main_kb)


async def main():
    bot = Bot(token=TOKEN)
    storage = RedisStorage.from_url('redis://localhost:6379/0')
    dp = Dispatcher()
    dp.include_router(liceychyk_router)  
    dp.include_router(router)
    dp.message.middleware.register(ThrottlingMiddleware(storage=storage))    
    print("✅ Бот запущено!")
    await dp.start_polling(bot)
    
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
