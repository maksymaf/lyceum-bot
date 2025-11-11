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
# from liceychyk import handle_liceychyk
import logging
logging.basicConfig(level=logging.INFO)

DATA_DIR = "data"
SCHEDULE_FILE = os.path.join(DATA_DIR, "schedule.json")
MENU_FILE = os.path.join(DATA_DIR, "menu.json")
ANNOUNCEMENTS_FILE = os.path.join(DATA_DIR, "announcements.json")
HELPERS_FILE = os.path.join(DATA_DIR, "helpers.json")
SUBSCRIBERS_FILE = os.path.join(DATA_DIR, "subscribers.json")

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

pending_announcements = {}

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Розклад"), KeyboardButton(text="📅 Завтра")],
        [KeyboardButton(text="🍲 Меню"), KeyboardButton(text="🧸 Мій Ліцейчик")],
        [KeyboardButton(text="📢 Оголошення")]
    ],
    resize_keyboard=True
)

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
    if message.from_user.id != ADMIN_USER_ID:
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

def get_announcement_kb(index: int, user_id: int):
    rows = []
    n = len(announcements)
    if n > 1:
        nav = []
        if index > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"ann_prev_{index-1}"))
        if index < n - 1:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"ann_next_{index+1}"))
        if nav:
            rows.append(nav)
    if user_id in ([ADMIN_USER_ID] + helpers):
        rows.append([InlineKeyboardButton(text="🗑 Видалити", callback_data=f"ann_del_{index}")])
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(Command("announce"))
async def cmd_announce(message: Message):
    if message.from_user.id not in ([ADMIN_USER_ID] + helpers):
        await message.answer("❌ У вас немає прав для цієї команди.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Напишіть повідомлення після команди:\n/announce Завтра збори батьків!")
        return
    text = parts[1].strip()
    if not text:
        await message.answer("Порожнє оголошення неможливе.")
        return
    pending_announcements[message.from_user.id] = text
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm_announce"),
            InlineKeyboardButton(text="❌ Відмінити", callback_data="cancel_announce")
        ]
    ])
    await message.answer(f"Підтвердити надсилання оголошення:\n\n{text}", reply_markup=kb)

@router.callback_query(lambda c: c.data in ["confirm_announce", "cancel_announce"])
async def confirm_or_cancel_announcement(callback: CallbackQuery):
    user_id = callback.from_user.id
    if callback.data == "cancel_announce":
        pending_announcements.pop(user_id, None)
        try: await callback.message.edit_text("❌ Оголошення скасовано.")
        except: pass
        await callback.answer()
        return
    text = pending_announcements.pop(user_id, None)
    if not text:
        await callback.answer("Немає оголошення для підтвердження.", show_alert=True)
        return
    announcements.append(text)
    save_json(ANNOUNCEMENTS_FILE, announcements)
    for user_id in subscribers:
        try:
           await callback.bot.send_message(chat_id=user_id, text=f"📢 {text}")
        except Exception as e:
           print(f"Не вдалося надіслати користувачу {user_id}: {e}")
    try: await callback.message.edit_text("✅ Оголошення надіслано й збережено.")
    except: pass
    await callback.answer()

@router.message(Command("announcements"))
async def cmd_announcements(message: Message):
    if not announcements:
        await message.answer("Немає оголошень.")
        return
    index = len(announcements) - 1
    text = f"📢 {announcements[index]}"
    kb = get_announcement_kb(index, message.from_user.id)
    await message.answer(text, reply_markup=kb)

@router.callback_query(lambda c: c.data and c.data.startswith("ann_"))
async def navigate_announcements(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 3: 
        await callback.answer(); return
    action, index = parts[1], int(parts[2])
    if action in ["next", "prev"]:
        if not (0 <= index < len(announcements)): await callback.answer(); return
        text = f"📢 {announcements[index]}"
        kb = get_announcement_kb(index, callback.from_user.id)
        try:
            if kb: await callback.message.edit_text(text, reply_markup=kb)
            else: await callback.message.edit_text(text)
        except: pass
        await callback.answer()
        return
    if action == "del":
        if callback.from_user.id not in ([ADMIN_USER_ID] + helpers):
            await callback.answer("❌ Немає прав.", show_alert=True); return
        if not (0 <= index < len(announcements)):
            await callback.answer("Помилка: індекс невалідний.", show_alert=True); return
        deleted = announcements.pop(index)
        save_json(ANNOUNCEMENTS_FILE, announcements)
        if announcements:
            new_index = min(index, len(announcements)-1)
            text = f"📢 {announcements[new_index]}"
            kb = get_announcement_kb(new_index, callback.from_user.id)
            try:
                if kb: await callback.message.edit_text(text, reply_markup=kb)
                else: await callback.message.edit_text(text)
            except: pass
        else:
            try: await callback.message.edit_text(f"🗑 Видалено оголошення:\n\n{deleted}\n\nНаразі немає оголошень.")
            except: pass
        await callback.answer("Видалено ✅")

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
