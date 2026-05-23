# 👑 LUXURY REFERRAL BOT
# Aiogram 3

import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

import os

TOKEN = os.getenv("TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# 👑 ENV VARIABLES
# TOKEN=bot_token
# BOT_USERNAME=your_bot
# ADMIN_ID=123456789
# 👑 LUXURY ADMIN SYSTEM ENABLED
ADMINS = [ADMIN_ID]
BANNED = []
# 👑 LUXURY INLINE ADMIN SYSTEM

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

SPONSORS = ["@telegram"]


class WithdrawState(StatesGroup):
    amount = State()


class RejectState(StatesGroup):
    reason = State()


async def db_start():
    db = await aiosqlite.connect("database.db")

    await db.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        referrer INTEGER,
        balance REAL DEFAULT 0,
        referrals INTEGER DEFAULT 0,
        bonus INTEGER DEFAULT 0
    )
    ''')

    await db.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        reward REAL DEFAULT 5,
        min_withdraw REAL DEFAULT 100
    )
    ''')

    await db.execute('''
    CREATE TABLE IF NOT EXISTS withdraws (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        status TEXT
    )
    ''')

    cur = await db.execute("SELECT * FROM settings")
    row = await cur.fetchone()

    if not row:
        await db.execute(
            "INSERT INTO settings (reward, min_withdraw) VALUES (?, ?)",
            (5, 100)
        )

    await db.commit()
    await db.close()


async def is_subscribed(user_id):
    for sponsor in SPONSORS:
        try:
            member = await bot.get_chat_member(sponsor, user_id)
            if member.status == "left":
                return False
        except:
            return False

    return True


async def get_settings():
    db = await aiosqlite.connect("database.db")
    cur = await db.execute("SELECT reward, min_withdraw FROM settings")
    row = await cur.fetchone()
    await db.close()
    return row


menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👑 Профиль")],
        [KeyboardButton(text="💎 Рефералы"), KeyboardButton(text="🏆 Топ")],
        [KeyboardButton(text="🎁 Бонус"), KeyboardButton(text="💸 Вывод")],
        [KeyboardButton(text="👑 Admin Panel")],
        [KeyboardButton(text="💸 Вывод")]
    ],
    resize_keyboard=True
)


@dp.message(CommandStart())
async def start(message: Message):
    args = message.text.split()
    referrer = None

    if len(args) > 1:
        try:
            referrer = int(args[1])
        except:
            pass

    db = await aiosqlite.connect("database.db")

    cur = await db.execute(
        "SELECT user_id FROM users WHERE user_id=?",
        (message.from_user.id,)
    )

    user = await cur.fetchone()

    if not user:
        await db.execute(
            "INSERT INTO users (user_id, referrer) VALUES (?, ?)",
            (message.from_user.id, referrer)
        )

        if referrer and referrer != message.from_user.id:
            reward, _ = await get_settings()

            await db.execute(
                "UPDATE users SET balance = balance + ?, referrals = referrals + 1 WHERE user_id=?",
                (reward, referrer)
            )

    await db.commit()
    await db.close()

    if not await is_subscribed(message.from_user.id):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📢 Подписаться", url="https://t.me/telegram")],
                [InlineKeyboardButton(text="✅ Проверить", callback_data="check_sub")]
            ]
        )

        return await message.answer(
            "<tg-emoji emoji-id='5359457415116417830'>👑</tg-emoji> <b>Подпишитесь на спонсоров</b>",
            reply_markup=kb
        )

    await message.answer(
        '''
<tg-emoji emoji-id="5359457415116417830">👑</tg-emoji> <b>WELCOME TO LUXURY REF SYSTEM</b>

<tg-emoji emoji-id="5431449001532594346">💎</tg-emoji> Приглашай друзей
<tg-emoji emoji-id="5194976881127989720">✨</tg-emoji> Зарабатывай баланс
<tg-emoji emoji-id="5465665476971471368">💸</tg-emoji> Выводи средства
''',
        reply_markup=menu
    )


@dp.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery):
    if not await is_subscribed(call.from_user.id):
        return await call.answer("❌ Вы не подписались", show_alert=True)

    await call.message.delete()

    await call.message.answer(
        "<tg-emoji emoji-id='5194976881127989720'>✅</tg-emoji> <b>Подписка подтверждена</b>",
        reply_markup=menu
    )


@dp.message(F.text == "👑 Профиль")
async def profile(message: Message):
    db = await aiosqlite.connect("database.db")

    cur = await db.execute(
        "SELECT balance, referrals FROM users WHERE user_id=?",
        (message.from_user.id,)
    )

    user = await cur.fetchone()
    reward, min_withdraw = await get_settings()

    text = f'''
<tg-emoji emoji-id="5267409167617398742">👑</tg-emoji> <b>LUXURY PROFILE</b>

🆔 ID: <code>{message.from_user.id}</code>
<tg-emoji emoji-id="5873149309456907997">👥</tg-emoji> Рефералов: <b>{user[1]}</b>
<tg-emoji emoji-id="5431449001532594346">💎</tg-emoji> Баланс: <b>{user[0]}₽</b>

<tg-emoji emoji-id="5282843764451195532">🎁</tg-emoji> За реферала: <b>{reward}₽</b>
<tg-emoji emoji-id="5465665476971471368">💸</tg-emoji> Мин. вывод: <b>{min_withdraw}₽</b>
'''

    await message.answer(text)
    await db.close()


@dp.message(F.text.startswith("/addadmin"))
async def add_admin(message: Message):
    if message.from_user.id not in ADMINS:
        return

    try:
        admin_id = int(message.text.split()[1])
    except:
        return await message.answer("❌ Пример: /addadmin 123")

    if admin_id not in ADMINS:
        ADMINS.append(admin_id)

    await message.answer(f"👑 Админ {admin_id} добавлен")


@dp.message(F.text.startswith("/deladmin"))
async def del_admin(message: Message):
    if message.from_user.id not in ADMINS:
        return

    try:
        admin_id = int(message.text.split()[1])
    except:
        return await message.answer("❌ Пример: /deladmin 123")

    if admin_id in ADMINS:
        ADMINS.remove(admin_id)

    await message.answer(f"❌ Админ {admin_id} удалён")


@dp.message(F.text.startswith("/give"))
async def give_balance(message: Message):
    if message.from_user.id not in ADMINS:
        return

    try:
        user_id = int(message.text.split()[1])
        amount = float(message.text.split()[2])
    except:
        return await message.answer("❌ Пример: /give id сумма")

    db = await aiosqlite.connect("database.db")

    await db.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id=?",
        (amount, user_id)
    )

    await db.commit()
    await db.close()

    await bot.send_message(
        user_id,
        f"<tg-emoji emoji-id='5194976881127989720'>✨</tg-emoji> Вам начислено <b>{amount}₽</b>"
    )

    await message.answer("✅ Баланс выдан")


@dp.message(F.text.startswith("/take"))
async def take_balance(message: Message):
    if message.from_user.id not in ADMINS:
        return

    try:
        user_id = int(message.text.split()[1])
        amount = float(message.text.split()[2])
    except:
        return await message.answer("❌ Пример: /take id сумма")

    db = await aiosqlite.connect("database.db")

    await db.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id=?",
        (amount, user_id)
    )

    await db.commit()
    await db.close()

    await message.answer("✅ Баланс снят")


@dp.message(F.text.startswith("/ban"))
async def ban_user(message: Message):
    if message.from_user.id not in ADMINS:
        return

    try:
        user_id = int(message.text.split()[1])
    except:
        return await message.answer("❌ Пример: /ban id")

    BANNED.append(user_id)

    await message.answer(f"🚫 Пользователь {user_id} забанен")


@dp.message(F.text.startswith("/unban"))
async def unban_user(message: Message):
    if message.from_user.id not in ADMINS:
        return

    try:
        user_id = int(message.text.split()[1])
    except:
        return await message.answer("❌ Пример: /unban id")

    if user_id in BANNED:
        BANNED.remove(user_id)

    await message.answer(f"✅ Пользователь {user_id} разбанен")


@dp.message(F.text.startswith("/user"))
async def user_info(message: Message):
    if message.from_user.id not in ADMINS:
        return

    try:
        user_id = int(message.text.split()[1])
    except:
        return await message.answer("❌ Пример: /user id")

    db = await aiosqlite.connect("database.db")

    cur = await db.execute(
        "SELECT balance, referrals FROM users WHERE user_id=?",
        (user_id,)
    )

    user = await cur.fetchone()
    await db.close()

    if not user:
        return await message.answer("❌ Пользователь не найден")

    await message.answer(f'''
<tg-emoji emoji-id="5267409167617398742">👑</tg-emoji> <b>USER PROFILE</b>

🆔 ID: <code>{user_id}</code>
👥 Рефералы: <b>{user[1]}</b>
💎 Баланс: <b>{user[0]}₽</b>
''')


@dp.message(F.text.startswith("/addsponsor"))
async def add_sponsor(message: Message):
    if message.from_user.id not in ADMINS:
        return

    try:
        sponsor = message.text.split()[1]
    except:
        return await message.answer("❌ Пример: /addsponsor @channel")

    SPONSORS.append(sponsor)

    await message.answer(f"📢 Спонсор {sponsor} добавлен")


@dp.message(F.text.startswith("/delsponsor"))
async def del_sponsor(message: Message):
    if message.from_user.id not in ADMINS:
        return

    try:
        sponsor = message.text.split()[1]
    except:
        return await message.answer("❌ Пример: /delsponsor @channel")

    if sponsor in SPONSORS:
        SPONSORS.remove(sponsor)

    await message.answer(f"❌ Спонсор {sponsor} удалён")


@dp.message(F.text == "👑 Admin Panel")
async def admin_panel(message: Message):
    if message.from_user.id not in ADMINS:
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="💰 Выдать баланс", callback_data="admin_give")],
            [InlineKeyboardButton(text="📢 Спонсоры", callback_data="admin_sponsors")],
            [InlineKeyboardButton(text="👑 Админы", callback_data="admin_admins")],
            [InlineKeyboardButton(text="🚫 Бан Система", callback_data="admin_ban")],
            [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast")]
        ]
    )

    await message.answer(
        "<tg-emoji emoji-id='5359457415116417830'>👑</tg-emoji> <b>LUXURY ADMIN PANEL</b>",
        reply_markup=kb
    )


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if call.from_user.id not in ADMINS:
        return

    db = await aiosqlite.connect("database.db")

    cur = await db.execute("SELECT COUNT(*) FROM users")
    users = (await cur.fetchone())[0]

    cur = await db.execute("SELECT COUNT(*) FROM withdraws")
    withdraws = (await cur.fetchone())[0]

    await db.close()

    await call.message.answer(f'''
<tg-emoji emoji-id="5222103143506736007">📊</tg-emoji> <b>BOT STATS</b>

👥 Пользователей: <b>{users}</b>
💸 Выводов: <b>{withdraws}</b>
👑 Админов: <b>{len(ADMINS)}</b>
📢 Спонсоров: <b>{len(SPONSORS)}</b>
''')


async def main():
    await db_start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
