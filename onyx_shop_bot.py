import os
import threading
import logging
from flask import Flask
from dotenv import load_dotenv
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))
MODERATION_CHAT_ID = int(os.getenv("MODERATION_CHAT_ID"))
REJECTED_CHAT_ID = int(os.getenv("REJECTED_CHAT_ID"))

# Flask
app = Flask(__name__)
@app.route("/", methods=["GET", "HEAD"])
def alive():
    return "Onyx Shop Bot is alive!", 200

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройки
RULES_TEXT = (
    "📝 Правила размещения объявлений:\n\n"
    "1. Не превышать 100 символов.\n"
    "2. Не использовать более 1 фото.\n"
    "3. Не использовать запрещённые слова (мат, ругательства и т.д.).\n"
    "4. Объявления можно публиковать не чаще чем раз в 2 часа.\n"
    "5. Объявление должно касаться только покупки, продажи, аренды или обмена."
)

SALE_KW = ["продажа", "продаю", "продам", "отдам", "sell", "селл", "сейл", "солью"]
BUY_KW = ["куплю", "покупка", "buy", "возьму", "заберу"]
TRADE_KW = ["обмен", "меняю", "trade", "swap"]
RENT_KW = ["сдам", "аренда", "арендую", "сниму", "rent"]
CAT_KW = ["nft", "чат", "канал", "доллары", "тон", "usdt", "звёзды", "подарки"]
FORBIDDEN = ["реклама", "спам", "ссылка", "instagram", "наркотики", "порн", "мошенничество", "ебать", "хуй", "сука", "подпишись", "заходи"]

POST_COOLDOWN = timedelta(hours=2)
last_post_time = {}
pending = {}
banned_users = set()

# Утилиты
def count_symbols(text: str) -> int:
    return len(text.strip())

def has_forbidden(text: str) -> bool:
    return any(f in text.lower() for f in FORBIDDEN)

def has_required(text: str) -> bool:
    lowered = text.lower()
    return any(k in lowered for k in SALE_KW + BUY_KW + TRADE_KW + RENT_KW)

def extract_tags(text: str) -> list[str]:
    tags = []
    words = text.lower().split()
    for word in words:
        if any(k in word for k in SALE_KW): tags.append("#продажа")
        if any(k in word for k in BUY_KW): tags.append("#покупка")
        if any(k in word for k in TRADE_KW): tags.append("#обмен")
        if any(k in word for k in RENT_KW): tags.append("#аренда")
        for c in CAT_KW:
            if c in word: tags.append(f"#{c}")
    return list(dict.fromkeys(tags))  # remove duplicates

def format_announcement(text: str, username: str) -> str:
    tags = extract_tags(text)
    first_tag = tags[0] if tags else "#объявление"
    return (
        f"Объявление | {first_tag}\n"
        f"-------------------\n"
        f"{text.strip()}\n\n"
        f"-------------------\n"
        f"Отправил(а): @{username}"
    )

def contact_button(user: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Написать продавцу", url=f"https://t.me/{user}")],
        [InlineKeyboardButton("Разместить объявление", url="https://t.me/onyxsh0pbot")]
    ])

def moderation_buttons(ad_id: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{ad_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{ad_id}")
    ]])

async def check_subscription(ctx: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await ctx.bot.get_chat_member(chat_id=TARGET_CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False

# Команды
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with open("onyxshopbot.png", "rb") as img:
        await update.message.reply_photo(
            photo=img,
            caption="Привет! Это бот магазина Onyx Shop. Чтобы опубликовать объявление — просто отправь его сюда. /rules"
        )

async def rules_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(RULES_TEXT)

async def cleartime_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == 5465504821:
        last_post_time.clear()
        await update.message.reply_text("✅ Все таймеры сброшены.")
    else:
        await update.message.reply_text("⛔ Нет доступа.")

async def ban_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 5465504821:
        return await update.message.reply_text("⛔ Нет доступа.")
    if not ctx.args:
        return await update.message.reply_text("⚠️ Используйте: /ban @username или /ban user_id")
    target = ctx.args[0].lstrip("@")
    try:
        banned_users.add(int(target))
        await update.message.reply_text(f"✅ Забанен ID: {target}")
    except ValueError:
        await update.message.reply_text("❌ Неверный ID")

async def unban_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 5465504821:
        return await update.message.reply_text("⛔ Нет доступа.")
    if not ctx.args:
        return await update.message.reply_text("⚠️ Используйте: /unban @username или /unban user_id")
    target = ctx.args[0].lstrip("@")
    try:
        banned_users.discard(int(target))
        await update.message.reply_text(f"✅ Разбанен ID: {target}")
    except ValueError:
        await update.message.reply_text("❌ Неверный ID")

# Обработка текста
async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user.username or "аноним"
    txt = update.message.text or ""

    if uid in banned_users:
        return await update.message.reply_text("⛔ Вы забанены и не можете публиковать объявления.")

    if not await check_subscription(ctx, uid):
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Подписаться", url=f"https://t.me/c/{str(TARGET_CHANNEL_ID)[4:]}")]])
        return await update.message.reply_text("❗ Подпишитесь на канал для публикации.", reply_markup=btn)

    now = datetime.utcnow()
    if uid in last_post_time and now - last_post_time[uid] < POST_COOLDOWN:
        wait = POST_COOLDOWN - (now - last_post_time[uid])
        return await update.message.reply_text(f"⏱ Следующее объявление можно через {wait.seconds // 60} мин.")

    if count_symbols(txt) > 100:
        return await update.message.reply_text("❌ Превышено 100 символов.")
    if has_forbidden(txt):
        return await update.message.reply_text("❌ Обнаружено запрещённое слово.")
    if not has_required(txt):
        return await update.message.reply_text("❌ Нет ключевых слов (продажа / покупка / аренда / обмен).")

    last_post_time[uid] = now
    await update.message.reply_text("✅ Объявление опубликовано.")
    msg = format_announcement(txt, user)
    await ctx.bot.send_message(chat_id=TARGET_CHANNEL_ID, text=msg, reply_markup=contact_button(user))
    await ctx.bot.send_message(chat_id=REJECTED_CHAT_ID, text=f"📩 @{user} (id: {uid}) опубликовал:\n{txt}")

# Обработка фото
async def photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user.username or "аноним"
    cap = update.message.caption or ""
    photos = update.message.photo or []
    mid = update.message.message_id

    if uid in banned_users:
        return await update.message.reply_text("⛔ Вы забанены и не можете публиковать объявления.")

    if not await check_subscription(ctx, uid):
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Подписаться", url=f"https://t.me/c/{str(TARGET_CHANNEL_ID)[4:]}")]])
        return await update.message.reply_text("❗ Подпишитесь на канал для публикации.", reply_markup=btn)

    if not photos:
        return await update.message.reply_text("❌ Прикрепите хотя бы одно фото.")

    if count_symbols(cap) > 100:
        return await update.message.reply_text("❌ Подпись превышает 100 символов.")
    if has_forbidden(cap):
        return await update.message.reply_text("❌ Запрещённое слово в подписи.")

    now = datetime.utcnow()
    if uid in last_post_time and now - last_post_time[uid] < POST_COOLDOWN:
        wait = POST_COOLDOWN - (now - last_post_time[uid])
        return await update.message.reply_text(f"⏱ Следующее объявление можно через {wait.seconds // 60} мин.")

    photo_id = photos[0].file_id

    if has_required(cap):
        last_post_time[uid] = now
        await update.message.reply_text("✅ Фото опубликовано.")
        await ctx.bot.send_photo(chat_id=TARGET_CHANNEL_ID, photo=photo_id, caption=format_announcement(cap, user), reply_markup=contact_button(user))
        await ctx.bot.send_message(chat_id=REJECTED_CHAT_ID, text=f"📷 @{user} (id: {uid}) опубликовал фото:\n{cap}")
    else:
        pending[mid] = {"type": "photo", "fid": photo_id, "cap": cap, "user": user, "uid": uid}
        await update.message.reply_text("🔎 Отправлено на модерацию.")
        await ctx.bot.send_photo(chat_id=MODERATION_CHAT_ID, photo=photo_id, caption=cap, reply_markup=moderation_buttons(mid))

# Модерация
async def mod_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    act, sid = q.data.split("_")
    ad = pending.pop(int(sid), None)
    if not ad:
        return await q.edit_message_text("❌ Уже обработано.")

    user = ad["user"]
    cap = ad.get("cap", "")
    uid = ad.get("uid")

    if act == "approve":
        last_post_time[uid] = datetime.utcnow()
        await ctx.bot.send_photo(
            chat_id=TARGET_CHANNEL_ID,
            photo=ad["fid"],
            caption=format_announcement(cap, user),
            reply_markup=contact_button(user)
        )
        await q.edit_message_text("✅ Одобрено и опубликовано.")
        await ctx.bot.send_message(chat_id=REJECTED_CHAT_ID, text=f"✅ @{user} (id: {uid}) опубликовал по модерации:\n{cap}")
    else:
        await q.edit_message_text("❌ Отклонено модератором.")
        await ctx.bot.send_message(chat_id=REJECTED_CHAT_ID, text=f"❌ Отклонено @{user} (id: {uid}):\n{cap}")

# Запуск
def run_bot():
    app_bt = ApplicationBuilder().token(TOKEN).build()
    app_bt.add_handler(CommandHandler("start", start_cmd))
    app_bt.add_handler(CommandHandler("rules", rules_cmd))
    app_bt.add_handler(CommandHandler("cleartime", cleartime_cmd))
    app_bt.add_handler(CommandHandler("ban", ban_cmd))
    app_bt.add_handler(CommandHandler("unban", unban_cmd))
    app_bt.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app_bt.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app_bt.add_handler(CallbackQueryHandler(mod_cb))

    logger.info("🚀 Бот запущен")
    app_bt.run_polling()

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8080), daemon=True).start()
    run_bot()
