import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

TOKEN = "TOKEN"
ADMIN_ID = 123456789
BOT_USERNAME = "YourBot"

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# ================= DATABASE =================

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0,
    referrals INTEGER DEFAULT 0,
    invited_by INTEGER,
    username TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS settings (
    ref_reward REAL DEFAULT 0.5,
    min_withdraw REAL DEFAULT 5
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS promo (
    code TEXT,
    reward REAL,
    uses INTEGER
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS promo_used (
    user_id INTEGER,
    code TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS withdrawals (
    user_id INTEGER,
    amount REAL,
    status TEXT
)
''')

conn.commit()

# ================= STATES =================

class WithdrawState(StatesGroup):
    amount = State()

class PromoState(StatesGroup):
    code = State()

class RejectState(StatesGroup):
    reason = State()

# ================= FUNCTIONS =================

def get_settings():
    row = cursor.execute("SELECT ref_reward, min_withdraw FROM settings").fetchone()

    if not row:
        cursor.execute("INSERT INTO settings VALUES (?, ?)", (0.5, 5))
        conn.commit()
        return 0.5, 5

    return row


def register_user(user_id, username, ref=None):
    user = cursor.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if user:
        return

    cursor.execute(
        "INSERT INTO users(user_id, username, invited_by) VALUES(?,?,?)",
        (user_id, username, ref)
    )

    if ref and ref != user_id:
        reward, _ = get_settings()

        cursor.execute(
            "UPDATE users SET balance = balance + ?, referrals = referrals + 1 WHERE user_id=?",
            (reward, ref)
        )

    conn.commit()


def get_user(user_id):
    return cursor.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,)
    ).fetchone()

# ================= KEYBOARDS =================

main_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="👥 Пригласить", callback_data="ref")],
        [InlineKeyboardButton(text="💸 Вывод", callback_data="withdraw")],
        [InlineKeyboardButton(text="🎁 Промокод", callback_data="promo")]
    ]
)

admin_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="💰 Настройки", callback_data="settings")]
    ]
)

# ================= START =================

@dp.message(CommandStart())
async def start(message: Message):
    args = message.text.split()

    ref = None

    if len(args) > 1:
        try:
            ref = int(args[1])
        except:
            pass

    register_user(
        message.from_user.id,
        message.from_user.username,
        ref
    )

    text = """
✨ <b>Добро пожаловать!</b>

💰 Зарабатывайте на приглашениях
👥 Приглашайте друзей
💸 Выводите деньги
🎁 Используйте промокоды
    """

    await message.answer(text, reply_markup=main_kb)

# ================= PROFILE =================

@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    user = get_user(callback.from_user.id)

    reward, minimum = get_settings()

    text = f"""
👤 <b>Ваш профиль</b>

🆔 ID: <code>{user[0]}</code>
💰 Баланс: <b>${user[1]:.2f}</b>
👥 Рефералов: <b>{user[2]}</b>

🎁 За реферала: <b>${reward}</b>
💸 Минимальный вывод: <b>${minimum}</b>
    """

    await callback.message.edit_text(text, reply_markup=main_kb)

# ================= REF =================

@dp.callback_query(F.data == "ref")
async def ref(callback: CallbackQuery):
    link = f"https://t.me/{BOT_USERNAME}?start={callback.from_user.id}"

    text = f"""
👥 <b>Ваша реферальная ссылка</b>

<code>{link}</code>

💰 Приглашайте друзей и зарабатывайте
    """

    await callback.message.edit_text(text, reply_markup=main_kb)

# ================= WITHDRAW =================

@dp.callback_query(F.data == "withdraw")
async def withdraw(callback: CallbackQuery, state: FSMContext):
    _, minimum = get_settings()

    await callback.message.answer(
        f"💸 Введите сумму вывода\nМинимум: ${minimum}"
    )

    await state.set_state(WithdrawState.amount)

@dp.message(WithdrawState.amount)
async def withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
    except:
        return await message.answer("❌ Введите число")

    user = get_user(message.from_user.id)
    _, minimum = get_settings()

    if amount < minimum:
        return await message.answer("❌ Сумма меньше минимальной")

    if amount > user[1]:
        return await message.answer("❌ Недостаточно средств")

    cursor.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id=?",
        (amount, message.from_user.id)
    )

    cursor.execute(
        "INSERT INTO withdrawals VALUES(?,?,?)",
        (message.from_user.id, amount, "pending")
    )

    conn.commit()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"accept_{message.from_user.id}_{amount}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject_{message.from_user.id}_{amount}"
                )
            ]
        ]
    )

    await bot.send_message(
        ADMIN_ID,
        f"""
💸 <b>Новая заявка на вывод</b>

👤 @{message.from_user.username}
🆔 <code>{message.from_user.id}</code>

💰 Сумма: <b>${amount}</b>
        """,
        reply_markup=kb
    )

    await message.answer("✅ Заявка отправлена")

    await state.clear()

# ================= ACCEPT =================

@dp.callback_query(F.data.startswith("accept_"))
async def accept(callback: CallbackQuery):
    data = callback.data.split("_")

    user_id = int(data[1])
    amount = float(data[2])

    await bot.send_message(
        user_id,
        f"""
✅ <b>Выплата подтверждена</b>

💰 Сумма: <b>${amount}</b>
        """
    )

    await callback.message.edit_text("✅ Выплата подтверждена")

# ================= REJECT =================

reject_data = {}

@dp.callback_query(F.data.startswith("reject_"))
async def reject(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split("_")

    user_id = int(data[1])
    amount = float(data[2])

    reject_data[callback.from_user.id] = (user_id, amount)

    await callback.message.answer("✍️ Введите причину отказа")

    await state.set_state(RejectState.reason)

@dp.message(RejectState.reason)
async def reject_reason(message: Message, state: FSMContext):
    user_id, amount = reject_data[message.from_user.id]

    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id=?",
        (amount, user_id)
    )

    conn.commit()

    await bot.send_message(
        user_id,
        f"""
❌ <b>Выплата отклонена</b>

📄 Причина:
{message.text}

💰 Деньги возвращены на баланс
        """
    )

    await message.answer("✅ Отказ отправлен")

    await state.clear()

# ================= PROMO =================

@dp.callback_query(F.data == "promo")
async def promo(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🎁 Введите промокод")

    await state.set_state(PromoState.code)

@dp.message(PromoState.code)
async def promo_check(message: Message, state: FSMContext):
    code = message.text.upper()

    promo = cursor.execute(
        "SELECT * FROM promo WHERE code=?",
        (code,)
    ).fetchone()

    if not promo:
        return await message.answer("❌ Промокод не найден")

    used = cursor.execute(
        "SELECT * FROM promo_used WHERE user_id=? AND code=?",
        (message.from_user.id, code)
    ).fetchone()

    if used:
        return await message.answer("❌ Вы уже использовали этот промокод")

    reward = promo[1]

    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id=?",
        (reward, message.from_user.id)
    )

    cursor.execute(
        "INSERT INTO promo_used VALUES(?,?)",
        (message.from_user.id, code)
    )

    conn.commit()

    await message.answer(
        f"✅ Промокод активирован\n💰 Получено: ${reward}"
    )

    await state.clear()

# ================= ADMIN =================

@dp.message(F.text == "/admin")
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "👑 Админ панель",
        reply_markup=admin_kb
    )

# ================= RUN =================

async def main():
    print("Bot started")
    await dp.start_polling(bot)

asyncio.run(main())
