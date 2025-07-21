import os
import logging
import threading
from dotenv import load_dotenv
from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ─── Конфиг ───────────────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))
MODERATION_CHAT_ID = int(os.getenv("MODERATION_CHAT_ID"))
REJECTED_CHAT_ID = int(os.getenv("REJECTED_CHAT_ID"))

# Flask для пинга Render
app = Flask(__name__)
@app.route("/")
def alive():
    return "Bot is alive!"

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Словари и списки ───────────────────────────────────────────────────
# Разрешённые спецсимволы (минимум для наглядности)
ALLOWED_SPECIAL = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?:;()[]{}@#$%^&*-+=_~<>/\\|'\"`")

# Ключевые слова по категориям
SALE_KW = ["продажа","продаю","sell","селл"]
BUY_KW  = ["куплю","покупка","buy"]
TRADE_KW= ["обмен","меняю","trade","swap"]
CAT_KW  = ["nft","чат","канал","доллары","тон","usdt","звёзды","подарки"]

# Запрещённые слова
FORBIDDEN = ["реклама","спам","ссылка","instagram","http","наркотики","порн","мошенничество","ебать","хуй","сука"]

# В очередь на модерацию
pending = {}

# ─── Утилиты ────────────────────────────────────────────────────────────
def normalize(text:str)->str:
    # Простая лат->кир замена (можно расширить)
    tr = str.maketrans("abectox","абестох")
    return text.translate(tr)

def has_forbidden(text:str)->bool:
    norm = normalize(text.lower())
    return any(f in norm for f in FORBIDDEN)

def has_required(text:str)->bool:
    norm = normalize(text.lower())
    return any(k in norm for k in (SALE_KW+BUY_KW+TRADE_KW))

def build_caption(text:str, username:str)->str:
    tags = []
    lw = text.lower().split()
    for w in lw:
        if any(k in w for k in SALE_KW):  tags.append("#продажа")
        if any(k in w for k in BUY_KW):   tags.append("#покупка")
        if any(k in w for k in TRADE_KW): tags.append("#обмен")
        for c in CAT_KW:
            if c in w: tags.append(f"#{c}")
    tags.append(f"@{username}")
    tags_line = " ".join(dict.fromkeys(tags))
    return f"{tags_line}\n\n{text.strip()}"

def contact_button(user):
    return InlineKeyboardMarkup([[InlineKeyboardButton("💬 Написать продавцу", url=f"https://t.me/{user}")]])

def moderation_buttons(ad_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{ad_id}"),
         InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{ad_id}")]
    ])

# ─── Хендлеры ───────────────────────────────────────────────────────────
async def start_cmd(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    logger.info(f"/start from @{update.effective_user.username}")
    with open("onyxshopbot.png","rb") as fp:
        await update.message.reply_photo(fp,
            caption="Привет! Это бот для публикации объявлений о продаже, покупке и обмене в @onyx_sh0p.\n"
                    "Просто пришлите мне текст или фото с подписью."
        )

async def text_handler(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    txt = update.message.text or ""
    user = update.effective_user.username or "аноним"
    mid = update.message.message_id

    logger.info(f"Text from @{user}: {txt}")

    # фильтры
    if has_forbidden(txt):
        return await update.message.reply_text("❌ Отклонено: найдено запрещённое слово.")
    if not has_required(txt):
        return await update.message.reply_text("❌ Отклонено: нет ключевых слов (куплю/продажа/обмен).")

    # автоматическая публикация
    await update.message.reply_text("✅ Объявление опубликовано.")
    await ctx.bot.send_message(
        chat_id=TARGET_CHANNEL_ID,
        text=build_caption(txt,user),
        reply_markup=contact_button(user)
    )

async def photo_handler(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    cap = update.message.caption or ""
    fid = update.message.photo[-1].file_id
    user = update.effective_user.username or "аноним"
    mid = update.message.message_id

    logger.info(f"Photo from @{user}, cap: {cap}")

    if has_forbidden(cap):
        return await update.message.reply_text("❌ Отклонено: найдено запрещённое слово.")
    if not has_required(cap):
        # на проверку
        pending[mid] = {"type":"photo","fid":fid,"cap":cap,"user":user}
        await update.message.reply_text("🔎 На модерацию.")
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

async def mod_cb(update:Update, ctx:ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    act,mid = q.data.split("_")
    ad = pending.pop(int(mid),None)
    if not ad:
        return await q.edit_message_text("❌ Уже обработано.")

    user, cap = ad["user"], ad.get("cap","")
    if act=="approve":
        # публикуем
        if ad["type"]=="photo":
            await ctx.bot.send_photo(
                chat_id=TARGET_CHANNEL_ID,
                photo=ad["fid"],
                caption=build_caption(cap,user),
                reply_markup=contact_button(user)
            )
        await q.edit_message_text("✅ Одобрено и опубликовано.")
    else:
        # отклонено
        await q.edit_message_text("❌ Отклонено модератором.")
        await ctx.bot.send_message(REJECTED_CHAT_ID,
            text=f"Отклонено @{user}:\n{cap}"
        )

# ─── Запуск ─────────────────────────────────────────────────────────────
def main():
    # Flask в фоне
    t=threading.Thread(target=app.run, kwargs={"host":"0.0.0.0","port":8080},daemon=True)
    t.start()

    # Telegram
    app_bt = ApplicationBuilder().token(TOKEN).build()
    app_bt.add_handler(CommandHandler("start", start_cmd))
    app_bt.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app_bt.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app_bt.add_handler(CallbackQueryHandler(mod_cb))

    logger.info("Запуск polling...")
    app_bt.run_polling()

if __name__=="__main__":
    main()
