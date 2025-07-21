import os
import threading
import logging
from flask import Flask
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ——— Загрузка конфигурации ——————————————————————————————
load_dotenv()
TOKEN              = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID  = int(os.getenv("TARGET_CHANNEL_ID"))
MODERATION_CHAT_ID = int(os.getenv("MODERATION_CHAT_ID"))
REJECTED_CHAT_ID   = int(os.getenv("REJECTED_CHAT_ID"))

# ——— Flask для пинга Render ———————————————————————————
app = Flask(__name__)
@app.route("/", methods=["GET", "HEAD"])
def alive():
    return "Onyx Shop Bot is alive!", 200

# ——— Логирование ——————————————————————————————————————
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ——— Списки ключевых и запрещённых слов —————————————————
SALE_KW   = ["продажа","продаю","sell","селл","сейл","аренда","сдам","солью"]
BUY_KW    = ["куплю","покупка","buy","возьму","заберу"]
TRADE_KW  = ["обмен","меняю","trade","swap"]
CAT_KW    = ["nft","чат","канал","доллары","тон","usdt","звёзды","подарки"]
FORBIDDEN = ["реклама","спам","ссылка","instagram","http","наркотики","порн","мошенничество","ебать","хуй","сука"]

pending = {}

def normalize(text: str) -> str:
    table = str.maketrans({
        "а": "a",  "б": "b",  "в": "v",  "г": "g",  "д": "d",
        "е": "e",  "ё": "e",  "ж": "zh", "з": "z",  "и": "i",
        "й": "y",  "к": "k",  "л": "l",  "м": "m",  "н": "n",
        "о": "o",  "п": "p",  "р": "r",  "с": "s",  "т": "t",
        "у": "u",  "ф": "f",  "х": "h",  "ц": "ts", "ч": "ch",
        "ш": "sh", "щ": "sh", "ъ": "_",  "ы": "y",  "ь": "_",
        "э": "e",  "ю": "yu", "я": "ya",
    })
    return text.translate(table)

def has_forbidden(text: str) -> bool:
    nt = normalize(text.lower())
    return any(f in nt for f in FORBIDDEN)

def has_required(text: str) -> bool:
    nt = normalize(text.lower())
    return any(k in nt for k in SALE_KW+BUY_KW+TRADE_KW)

def build_caption(text: str, user: str) -> str:
    tags = []
    words = text.lower().split()
    for w in words:
        if any(k in w for k in SALE_KW):   tags.append("#продажа")
        if any(k in w for k in BUY_KW):    tags.append("#покупка")
        if any(k in w for k in TRADE_KW):  tags.append("#обмен")
        for c in CAT_KW:
            if c in w: tags.append(f"#{c}")
    tags.append(f"@{user}")
    # уникализируем, сохраняем порядок
    seen = set(); uniq = []
    for t in tags:
        if t not in seen:
            seen.add(t); uniq.append(t)
    return " ".join(uniq) + "\n\n" + text.strip()

def contact_button(user: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Написать продавцу", url=f"https://t.me/{user}")],
        [InlineKeyboardButton("Разместить объявление", url="https://t.me/onyxsh0pbot")]
    ])


def moderation_buttons(ad_id: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{ad_id}"),
        InlineKeyboardButton("❌ Отклонить",  callback_data=f"reject_{ad_id}")
    ]])

def format_announcement(text: str, username: str) -> str:
    return (
        "Объявление\n"
        "--------------------\n"
        f"{text.strip()}\n"
        "--------------------\n"
        f"Отправил(а): @{username}"
    )


# ——— Хендлеры ——————————————————————————————————————
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/start from @{update.effective_user.username}")
    with open("onyxshopbot.png","rb") as img:
        await update.message.reply_photo(
            photo=img,
            caption=(
                "Привет! Это бот магазина Onyx Shop.\n"
                "Чтобы выложить объявление просто отправьте его боту (до 100 символов, не более одной картинки)"
            )
        )

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt  = update.message.text or ""
    user = update.effective_user.username or "аноним"
    mid  = update.message.message_id
    logger.info(f"Text from @{user}: {txt}")

    if has_forbidden(txt):
        return await update.message.reply_text("❌ Отклонено: найдено запрещённое слово.")
    if not has_required(txt):
        return await update.message.reply_text("❌ Отклонено: нет ключевых слов (куплю/продажа/обмен).")

    # автоматическая публикация
    await update.message.reply_text("✅ Объявление опубликовано.")
    await ctx.bot.send_message(
        chat_id=TARGET_CHANNEL_ID,
        text=format_announcement(txt, user),
        reply_markup=contact_button(user)
    )

async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cap  = update.message.caption or ""
    fid  = update.message.photo[-1].file_id
    user = update.effective_user.username or "аноним"
    mid  = update.message.message_id
    logger.info(f"Photo from @{user}, cap: {cap}")

    if has_forbidden(cap):
        return await update.message.reply_text("❌ Фото отклонено: найдено запрещённое слово.")
    if not has_required(cap):
        # отправляем на модерацию
        pending[mid] = {"type":"photo","fid":fid,"cap":cap,"user":user}
        await update.message.reply_text("🔎 Фото отправлено на модерацию.")
        return await ctx.bot.send_photo(
            chat_id=MODERATION_CHAT_ID,
            photo=fid,
            caption=cap,
            reply_markup=moderation_buttons(mid)
        )

    # автоматическая публикация
    await update.message.reply_text("✅ Фото опубликовано.")
    await ctx.bot.send_photo(
        chat_id=TARGET_CHANNEL_ID,
        photo=fid,
        caption=build_caption(cap,user),
        reply_markup=contact_button(user)
    )

async def mod_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    act, sid = q.data.split("_")
    ad = pending.pop(int(sid), None)

    if not ad:
        return await q.edit_message_text("❌ Уже обработано.")

    user = ad["user"]
    cap = ad.get("cap", "")

    if act == "approve":
        if ad["type"] == "photo":
            await ctx.bot.send_photo(
                chat_id=TARGET_CHANNEL_ID,
                photo=ad["fid"],
                caption=format_announcement(cap, user),
                reply_markup=contact_button(user)
            )
        else:
            await ctx.bot.send_message(
                chat_id=TARGET_CHANNEL_ID,
                text=format_announcement(cap, user),
                reply_markup=contact_button(user)
            )
        await q.edit_message_text("✅ Одобрено и опубликовано.")
    else:
        await q.edit_message_text("❌ Отклонено модератором.")
        await ctx.bot.send_message(
            chat_id=REJECTED_CHAT_ID,
            text=f"Отклонено @{user}:\n{cap}"
        )



# ——— Запуск бота ——————————————————————————————————————
def run_bot():
    app_bt = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )
    app_bt.add_handler(CommandHandler("start",    start_cmd))
    app_bt.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app_bt.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app_bt.add_handler(CallbackQueryHandler(mod_cb))

    logger.info("🚀 Telegram polling стартовал")
    app_bt.run_polling()

# ——— Точка входа ——————————————————————————————————————
if __name__ == "__main__":
    # Flask держит процесс живым
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=8080),
        daemon=True
    ).start()
    run_bot()
