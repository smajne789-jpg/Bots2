# GIVEAWAY BOT (UPDATED LOGIC: manual subscribe text + enforced check)

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import random
import logging
import os

API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_states = {}
giveaways = {}

# ================= UI =================

def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎁 Создать", callback_data="create"))
    kb.add(InlineKeyboardButton("📋 Мои", callback_data="my"))
    return kb


def sub_choice_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Да (проверять)", callback_data="sub_yes"))
    kb.add(InlineKeyboardButton("❌ Нет", callback_data="sub_no"))
    return kb

# ================= START =================

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Меню:", reply_markup=main_menu())

# ================= CREATE =================

@dp.callback_query_handler(lambda c: c.data == "create")
async def create(call: types.CallbackQuery):
    user_states[call.from_user.id] = {"step": "title"}
    await call.message.answer("Название:")


@dp.message_handler()
async def steps(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    state = user_states.get(message.from_user.id)
    if not state:
        return

    step = state["step"]

    if step == "title":
        state["title"] = message.text
        state["step"] = "desc"
        await message.answer("Описание (сюда пишешь условия сам, например подписку):")

    elif step == "desc":
        state["desc"] = message.text
        state["step"] = "winners"
        await message.answer("Победителей:")

    elif step == "winners":
        if not message.text.isdigit():
            await message.answer("Число")
            return

        state["winners"] = int(message.text)
        state["step"] = "sub_check"
        await message.answer("Проверять подписку?", reply_markup=sub_choice_kb())


# ================= SUB CHOICE =================

@dp.callback_query_handler(lambda c: c.data in ["sub_yes", "sub_no"])
async def sub_choice(call: types.CallbackQuery):
    state = user_states.get(call.from_user.id)

    if call.data == "sub_yes":
        state["check_sub"] = True
    else:
        state["check_sub"] = False

    await publish(call.message, state)

# ================= PUBLISH =================

async def publish(message, state):
    gid = str(len(giveaways) + 1)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🎉 Участвовать", callback_data=f"join_{gid}"))

    text = f"🎁 {state['title']}\n\n{state['desc']}\n\n🏆 Победителей: {state['winners']}"

    msg = await bot.send_message(CHANNEL_ID, text, reply_markup=kb)

    giveaways[gid] = {
        "id": gid,
        "title": state["title"],
        "desc": state["desc"],
        "winners": state["winners"],
        "participants": [],
        "finished": False,
        "msg_id": msg.message_id,
        "check_sub": state["check_sub"]
    }

    user_states.pop(message.chat.id, None)

    await message.answer("Опубликовано", reply_markup=main_menu())

# ================= JOIN =================

@dp.callback_query_handler(lambda c: c.data.startswith("join_"))
async def join(call: types.CallbackQuery):
    gid = call.data.split("_")[1]
    g = giveaways.get(gid)

    if g["finished"]:
        await call.answer("Завершено", show_alert=True)
        return

    user_id = call.from_user.id

    if g["check_sub"]:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status == "left":
            await call.answer("Сначала подпишись на канал", show_alert=True)
            return

    if user_id in g["participants"]:
        await call.answer("Уже участвуешь")
        return

    g["participants"].append(user_id)
    await call.answer("Ты участвуешь")

# ================= MY =================

@dp.callback_query_handler(lambda c: c.data == "my")
async def my(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup()

    for gid, g in giveaways.items():
        if not g["finished"]:
            kb.add(InlineKeyboardButton(f"❌ {g['title']}", callback_data=f"finish_{gid}"))

    await call.message.answer("Завершить:", reply_markup=kb)

# ================= FINISH =================

@dp.callback_query_handler(lambda c: c.data.startswith("finish_"))
async def finish(call: types.CallbackQuery):
    gid = call.data.split("_")[1]
    g = giveaways.get(gid)

    if not g["participants"]:
        await call.answer("Нет участников")
        return

    winners = random.sample(g["participants"], min(len(g["participants"]), g["winners"]))

    g["finished"] = True

    text = "🏆 Победители:\n" + "\n".join([f"<a href='tg://user?id={w}'>Победитель</a>" for w in winners])

    await bot.send_message(CHANNEL_ID, text, parse_mode="HTML")
    await call.answer("Готово")

# ================= RUN =================

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
