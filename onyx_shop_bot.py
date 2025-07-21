import os
import threading
import logging
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv

# Загружаем токены из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID")
MODERATION_CHAT_ID = os.getenv("MODERATION_CHAT_ID")
REJECTED_CHAT_ID = os.getenv("REJECTED_CHAT_ID")

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Список запрещённых слов
FORBIDDEN_WORDS = {"обман", "мошенничество", "scam"}

# Инициализация Flask
app = Flask(__name__)

# ===== Утилиты =====
def normalize_text(text: str) -> str:
    translation = str.maketrans(
        "àáäâçèéëêìíïîñòóöôùúüû",
        "aaaaçeeeeiiiinoooouuuu"
    )
    return text.translate(translation)

def contains_forbidden_words(text: str) -> bool:
    normalized_text = normalize_text(text.lower())
    return any(word in normalized_text for word in FORBIDDEN_WORDS)

# ===== Хендлеры Telegram =====
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["📢 Разместить объявление"]]
    reply_markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    # Отправка изображения + текста
    photo_path = os.path.join(os.path.dirname(__file__), "onyxshopbot.png")
    with open(photo_path, "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption="Добро пожаловать в Onyx Shop Bot!\n\nНажмите кнопку ниже, чтобы разместить объявление.",
            reply_markup=reply_markup,
        )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.message.from_user.id

    if contains_forbidden_words(text):
        await update.message.reply_text("🚫 Ваше сообщение содержит запрещённые слова и было отклонено.")
        return

    # Сохраняем сообщение ID, чтобы потом обработать
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve|{user_id}|{update.message.message_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject|{user_id}|{update.message.message_id}"),
        ]
    ])

    await context.bot.send_message(
        chat_id=MODERATION_CHAT_ID,
        text=f"Новое объявление от пользователя {user_id}:\n\n{text}",
        reply_markup=keyboard
    )

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🖼 Спасибо за изображение! Оно будет рассмотрено модератором.")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")

    if len(data) != 3:
        await query.edit_message_text("❗ Ошибка в формате callback data.")
        return

    action, user_id, message_id = data
    user_id = int(user_id)
    message_id = int(message_id)

    try:
        # Получаем оригинальное сообщение
        msg = await context.bot.forward_message(
            chat_id=context.bot.id,
            from_chat_id=user_id,
            message_id=message_id
        )

        if action == "approve":
            await context.bot.send_message(chat_id=TARGET_CHANNEL_ID, text=msg.text)
            await query.edit_message_text("✅ Объявление одобрено и опубликовано.")
        elif action == "reject":
            await context.bot.send_message(chat_id=REJECTED_CHAT_ID, text=msg.text)
            await query.edit_message_text("❌ Объявление отклонено.")
    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}")
        await query.edit_message_text("⚠️ Не удалось обработать объявление.")

# ===== Запуск Telegram Bot =====
def run_bot():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("✅ Telegram бот запущен.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

# ===== Flask роут =====
@app.route("/", methods=["GET", "HEAD"])
def index():
    return "✅ Onyx Shop Bot работает!", 200

# ===== Точка запуска =====
if __name__ == "__main__":
    # Запускаем бота в отдельном потоке
    threading.Thread(target=run_bot, daemon=True).start()
    logger.info("🚀 Flask сервер запущен на Render.")
    app.run(host="0.0.0.0", port=8080)
