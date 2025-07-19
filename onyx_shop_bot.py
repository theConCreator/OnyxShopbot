import os
from dotenv import load_dotenv
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler)
from flask import Flask
import threading

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))
MODERATION_CHAT_ID = int(os.getenv("MODERATION_CHAT_ID"))
REJECTED_CHAT_ID = int(os.getenv("REJECTED_CHAT_ID"))

app = Flask(__name__)

# Flask fake ping route to keep bot alive on Render
@app.route('/')
def index():
    return "Bot is running."

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# In-memory moderation queue
pending_approvals = {}

# Allowed and denied content settings
ALLOWED_LANGS = ["en", "ru"]
ALLOWED_SPECIAL_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?:;()[]{}@#$%^&*-+=_~<>/\\\\|'\"`♡❤•₽¥€$£₿🙂🙃😀😂😅😊😉👍🔥💎🚀✨🎁💰🎉💬")

SALE_KEYWORDS = ["продажа", "продаю", "sell", "селл", "s"]
BUY_KEYWORDS = ["куплю", "покупка", "buy", "b"]
TRADE_KEYWORDS = ["обмен", "меняю", "trade", "swap"]
CATEGORY_KEYWORDS = ["nft", "чат", "канал", "доллары", "тон", "usdt", "звёзды", "гив", "nft подарок", "подарки"]
FORBIDDEN_WORDS = ["реклама", "подпишись", "подписка", "реферал", "ссылка", "instagram", "youtube", "tiktok", "http", "www", ".com", ".ru"]

# Build simple caption without hashtags
def build_caption(text: str, username: str, price: str = None):
    user_mention = f"@{username}" if username else "пользователь скрыл имя"
    price_line = f"\nЦена: {price}" if price else ""
    caption = f"""
Объявление:

{text.strip()}

{price_line}

Опубликовал(а): {user_mention}

Написать продавцу: [Написать](https://t.me/{username})
    """
    return caption[:1024]  # Ограничение по символам Telegram

# Create contact button
def contact_seller_button(username: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Написать продавцу", url=f"https://t.me/{username}")]
    ])

def moderation_buttons(ad_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Одобрить", callback_data=f"approve_{ad_id}"),
            InlineKeyboardButton("Отклонить", callback_data=f"reject_{ad_id}")
        ]
    ])

def is_valid_ad(text: str):
    text_lower = text.lower()
    if any(word in text_lower for word in FORBIDDEN_WORDS):
        return False
    if not any(kw in text_lower for kw in SALE_KEYWORDS + BUY_KEYWORDS + TRADE_KEYWORDS):
        return False
    return all(char in ALLOWED_SPECIAL_CHARS for char in text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Это бот для публикации объявлений о продаже, покупке и обмене в @onyx_sh0p.\n"
        "Для отправки просто пришлите объявление боту."
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    username = update.message.from_user.username or "аноним"
    # Добавление цены, если она указана
    price = None
    if "Цена:" in text:
        text, price = text.split("Цена:", 1)
        price = price.strip()

    if is_valid_ad(text):
        await update.message.reply_text("✅ Объявление принято и опубликовано.")
        await context.bot.send_message(
            chat_id=TARGET_CHANNEL_ID,
            text=build_caption(text, username, price),
            reply_markup=contact_seller_button(username)
        )
    else:
        ad_id = update.message.message_id
        pending_approvals[ad_id] = {"type": "text", "text": text, "username": username, "price": price}
        await context.bot.send_message(
            chat_id=MODERATION_CHAT_ID,
            text=f"Новое текстовое объявление на модерацию:\n{text}",
            reply_markup=moderation_buttons(ad_id)
        )
        await update.message.reply_text("🔎 Объявление отправлено на модерацию.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption or ""  # Если caption нет, используем пустую строку
    file_id = update.message.photo[-1].file_id
    username = update.message.from_user.username or "аноним"
    
    # Аналогично добавим цену
    price = None
    if "Цена:" in caption:
        caption, price = caption.split("Цена:", 1)
        price = price.strip()

    if is_valid_ad(caption):
        await update.message.reply_text("✅ Фотообъявление принято и опубликовано.")
        await context.bot.send_photo(
            chat_id=TARGET_CHANNEL_ID,
            photo=file_id,
            caption=build_caption(caption, username, price),
            reply_markup=contact_seller_button(username)
        )
    else:
        ad_id = update.message.message_id
        pending_approvals[ad_id] = {"type": "photo", "text": caption, "file_id": file_id, "username": username, "price": price}
        await context.bot.send_photo(
            chat_id=MODERATION_CHAT_ID,
            photo=file_id,
            caption=f"Новое фотообъявление на модерацию:\n{caption}",
            reply_markup=moderation_buttons(ad_id)
        )
        await update.message.reply_text("🔎 Фотообъявление отправлено на модерацию.")

async def handle_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, ad_id = query.data.split("_")
    ad = pending_approvals.pop(int(ad_id), None)
    if not ad:
        await query.edit_message_text("❗️ Объявление уже обработано.")
        return

    username = ad.get("username", "аноним")
    if action == "approve":
        if ad["type"] == "photo":
            await context.bot.send_photo(
                chat_id=TARGET_CHANNEL_ID,
                photo=ad["file_id"],
                caption=build_caption(ad["text"], username, ad["price"]),
                reply_markup=contact_seller_button(username)
            )
        else:
            await context.bot.send_message(
                chat_id=TARGET_CHANNEL_ID,
                text=build_caption(ad["text"], username, ad["price"]),
                reply_markup=contact_seller_button(username)
            )
        await query.edit_message_text("✅ Объявление одобрено и опубликовано.")
    else:
        await context.bot.send_message(REJECTED_CHAT_ID, f"🚫 Отклонено:\n{ad['text']}")
        await query.edit_message_text("❌ Объявление отклонено.")

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_moderation))

    app.run_polling()

