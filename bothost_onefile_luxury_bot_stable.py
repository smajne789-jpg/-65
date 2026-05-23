import asyncio
import os
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import *
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# ================== CONFIG ==================
TOKEN = os.getenv("TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

SPONSORS = [
    "@telegram"
]

# ================== BOT ==================
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

# ================== DATABASE ==================
def db():
    return sqlite3.connect("database.db")

conn = db()
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
user_id INTEGER PRIMARY KEY,
referrer INTEGER,
balance REAL DEFAULT 0,
refs INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS settings(
reward REAL DEFAULT 5,
min_withdraw REAL DEFAULT 100
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS withdraws(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
amount REAL,
status TEXT
)
""")

conn.commit()

cur.execute("SELECT * FROM settings")
if not cur.fetchone():
    cur.execute("INSERT INTO settings VALUES(5,100)")
    conn.commit()

# ================== STATES ==================
class Withdraw(StatesGroup):
    amount = State()

class Reject(StatesGroup):
    reason = State()

# ================== MENU ==================
menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👑 Профиль")],
        [KeyboardButton(text="💎 Рефералы"), KeyboardButton(text="🏆 Топ")],
        [KeyboardButton(text="🎁 Бонус"), KeyboardButton(text="💸 Вывод")],
        [KeyboardButton(text="👑 Админка")]
    ],
    resize_keyboard=True
)

# ================== FUNCTIONS ==================
def get_settings():
    c = db().cursor()
    c.execute("SELECT reward, min_withdraw FROM settings")
    return c.fetchone()

async def subscribed(user_id):
    for sponsor in SPONSORS:
        try:
            member = await bot.get_chat_member(sponsor, user_id)
            if member.status == "left":
                return False
        except:
            return False
    return True

# ================== START ==================
@dp.message(CommandStart())
async def start(message: Message):
    args = message.text.split()
    ref = None

    if len(args) > 1:
        try:
            ref = int(args[1])
        except:
            pass

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE user_id=?", (message.from_user.id,))
    user = cur.fetchone()

    if not user:
        cur.execute(
            "INSERT INTO users(user_id, referrer) VALUES(?, ?)",
            (message.from_user.id, ref)
        )

        if ref and ref != message.from_user.id:
            reward, _ = get_settings()

            cur.execute(
                "UPDATE users SET balance = balance + ?, refs = refs + 1 WHERE user_id=?",
                (reward, ref)
            )

            try:
                await bot.send_message(
                    ref,
                    f"✨ Вам начислено <b>{reward}₽</b> за реферала"
                )
            except:
                pass

        conn.commit()

    if not await subscribed(message.from_user.id):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📢 Подписаться", url="https://t.me/telegram")],
                [InlineKeyboardButton(text="✅ Проверить", callback_data="check_sub")]
            ]
        )

        return await message.answer(
            "👑 Подпишитесь на спонсоров",
            reply_markup=kb
        )

    await message.answer(
        """
👑 <b>LUXURY REF SYSTEM</b>

💎 Приглашай друзей
💸 Получай баланс
🏆 Выводи деньги
        """,
        reply_markup=menu
    )

# ================== SUB CHECK ==================
@dp.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery):
    if not await subscribed(call.from_user.id):
        return await call.answer("❌ Подпишитесь", show_alert=True)

    await call.message.answer("✅ Подписка подтверждена", reply_markup=menu)

# ================== PROFILE ==================
@dp.message(F.text == "👑 Профиль")
async def profile(message: Message):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance, refs FROM users WHERE user_id=?",
        (message.from_user.id,)
    )

    user = cur.fetchone()
    reward, minimum = get_settings()

    text = f"""
👑 <b>ПРОФИЛЬ</b>

🆔 ID: <code>{message.from_user.id}</code>
👥 Рефералов: <b>{user[1]}</b>
💎 Баланс: <b>{user[0]}₽</b>

🎁 За реферала: <b>{reward}₽</b>
💸 Мин вывод: <b>{minimum}₽</b>
"""

    await message.answer(text)

# ================== REFS ==================
@dp.message(F.text == "💎 Рефералы")
async def refs(message: Message):
    link = f"https://t.me/{BOT_USERNAME}?start={message.from_user.id}"

    await message.answer(
        f"👥 Ваша ссылка:\n\n<code>{link}</code>"
    )

# ================== TOP ==================
@dp.message(F.text == "🏆 Топ")
async def top(message: Message):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT user_id, refs FROM users ORDER BY refs DESC LIMIT 10")
    users = cur.fetchall()

    text = "🏆 <b>ТОП</b>\n\n"

    for i, u in enumerate(users, start=1):
        text += f"{i}. <code>{u[0]}</code> — {u[1]}\n"

    await message.answer(text)

# ================== BONUS ==================
@dp.message(F.text == "🎁 Бонус")
async def bonus(message: Message):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET balance = balance + 10 WHERE user_id=?",
        (message.from_user.id,)
    )

    conn.commit()

    await message.answer("🎁 Вам начислено 10₽")

# ================== WITHDRAW ==================
@dp.message(F.text == "💸 Вывод")
async def withdraw(message: Message, state: FSMContext):
    await state.set_state(Withdraw.amount)
    await message.answer("💸 Введите сумму")

@dp.message(Withdraw.amount)
async def withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
    except:
        return await message.answer("❌ Введите число")

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id=?",
        (message.from_user.id,)
    )

    balance = cur.fetchone()[0]
    _, minimum = get_settings()

    if amount < minimum:
        return await message.answer(f"❌ Мин вывод {minimum}₽")

    if balance < amount:
        return await message.answer("❌ Недостаточно средств")

    cur.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id=?",
        (amount, message.from_user.id)
    )

    cur.execute(
        "INSERT INTO withdraws(user_id, amount, status) VALUES(?,?,?)",
        (message.from_user.id, amount, "wait")
    )

    wid = cur.lastrowid
    conn.commit()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"ok_{wid}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"no_{wid}")
            ]
        ]
    )

    await bot.send_message(
        ADMIN_ID,
        f"💸 Новая заявка\n\n👤 @{message.from_user.username}\n💰 {amount}₽",
        reply_markup=kb
    )

    await message.answer("✅ Заявка отправлена")
    await state.clear()

# ================== ACCEPT ==================
@dp.callback_query(F.data.startswith("ok_"))
async def accept(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    wid = int(call.data.split("_")[1])

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT user_id, amount FROM withdraws WHERE id=?", (wid,))
    data = cur.fetchone()

    if not data:
        return

    user_id, amount = data

    cur.execute(
        "UPDATE withdraws SET status='done' WHERE id=?",
        (wid,)
    )

    conn.commit()

    await bot.send_message(
        user_id,
        f"✅ Выплата подтверждена\n\n💸 {amount}₽"
    )

    await call.message.edit_text("✅ Выплата подтверждена")

# ================== REJECT ==================
@dp.callback_query(F.data.startswith("no_"))
async def reject(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return

    wid = int(call.data.split("_")[1])

    await state.update_data(wid=wid)
    await state.set_state(Reject.reason)

    await call.message.answer("❌ Введите причину отказа")

@dp.message(Reject.reason)
async def reject_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    wid = data['wid']

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id, amount FROM withdraws WHERE id=?",
        (wid,)
    )

    user_id, amount = cur.fetchone()

    cur.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id=?",
        (amount, user_id)
    )

    cur.execute(
        "UPDATE withdraws SET status='reject' WHERE id=?",
        (wid,)
    )

    conn.commit()

    await bot.send_message(
        user_id,
        f"❌ Заявка отклонена\n\n📄 Причина: {message.text}\n\n💰 Деньги возвращены"
    )

    await message.answer("✅ Заявка отклонена")
    await state.clear()

# ================== ADMIN ==================
@dp.message(F.text == "👑 Админка")
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM withdraws")
    withdraws = cur.fetchone()[0]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Обновить", callback_data="stats")]
        ]
    )

    await message.answer(
        f"""
👑 <b>ADMIN PANEL</b>

👥 Пользователей: <b>{users}</b>
💸 Выводов: <b>{withdraws}</b>
📢 Спонсоров: <b>{len(SPONSORS)}</b>
        """,
        reply_markup=kb
    )

# ================== RUN ==================
async def main():
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
