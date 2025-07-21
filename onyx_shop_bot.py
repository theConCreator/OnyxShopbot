import os
import threading
import logging
from flask import Flask
from telegram import Update, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Telegram настройки
TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID")
MODERATION_CHAT_ID = os.getenv("MODERATION_CHAT_ID")
REJECTED_CHAT_ID = os.getenv("REJECTED_CHAT_ID")

# Flask app
app = Flask(__name__)

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Запрещённые слова
FORBIDDEN_WORDS = {"обман", "мошенничество", "scam"}

# ==== Вспомогательные функции ====
def normalize_text(text: str) -> str:
    translation = str.maketrans(
        "àáäâçèéëêìíïîñòóöôùúüû",
        "aaaaçeeeeiiiinoooouuuu"
    )
    return text.translate(translation)

def contains_forbidden_words(text: str) -> bool:
    normalized_text = normalize_text(text.lower())
    return any(word in normalized_text for word in FORBIDDEN_WORDS)

# ==== Хэндлеры ====
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_keyboard = [["📢 Разместить объявление"]]
    reply_markup = context.bot.keyboard_markup(keyboard=menu_keyboard, resize_keyboard=True)

    photo_path = os.path.join(os.path.dirname(__file__), "onyxshopbot.png")
    with open(photo_path, "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption="Добро пожаловать в Onyx Shop Bot!\n\nНажмите кнопку ниже, чтобы разместить объявление.",
            reply_markup=reply_markup,
        )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if contains_forbidden_words(text):
        await update.message.reply_text("🚫 Ваше сообщение содержит запрещённые слова и было отклонено.")
        return

    # Отправка на модерацию
    keyboard = [
        [
            {"text": "✅ Одобрить", "callback_data": f"approve|{update.message.chat.id}|{update.message.message_id}"},
            {"text": "❌ Отклонить", "callback_data": f"reject|{update.message.chat.id}|{update.message.message_id}"},
        ]
    ]
    await context.bot.send_message(
        chat_id=MODERATION_CHAT_ID,
        text=f"Новое сообщение:\n\n{text}",
        reply_markup=context.bot.inline_keyboard_markup(keyboard)
    )

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🖼 Спасибо за изображение! Оно будет рассмотрено модератором.")

async def mod_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|")
    action, user_id, msg_id = data[0], int(data[1]), int(data[2])

    original_msg = await context.bot.forward_message(chat_id=user_id, from_chat_id=user_id, message_id=msg_id)

    if action == "approve":
        await context.bot.send_message(chat_id=TARGET_CHANNEL_ID, text=original_msg.text)
        await query.edit_message_text("✅ Объявление одобрено и опубликовано.")
    elif action == "reject":
        await context.bot.send_message(chat_id=REJECTED_CHAT_ID, text=original_msg.text)
        await query.edit_message_text("❌ Объявление отклонено и отправлено в архив.")

# ==== Telegram bot запуск ====
def run_bot():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(CallbackQueryHandler(mod_cb))

    logger.info("Бот запущен (polling)")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

# ==== Flask запускается как основной процесс ====
@app.route("/", methods=["GET", "HEAD"])
def index():
    return "Onyx Bot is running!", 200

@app.before_first_request
def activate_bot():
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    logger.info("Запуск Flask для Render...")
    app.run(host="0.0.0.0", port=8080)
