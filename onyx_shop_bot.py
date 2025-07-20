import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import multiprocessing
from flask import Flask
import asyncio

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))

# Flask приложение
app = Flask(__name__)

@app.route('/')
def index():
    return 'Bot is alive!'

# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Список разрешённых слов
ALLOWED_KEYWORDS = ["покупка", "продажа", "обмен", "sell", "продаю", "куплю", "trade", "buy"]

# Запрещённые слова
FORBIDDEN_WORDS = ["реклама", "спам", "порнография", "наркотики", "мошенничество", "терроризм"]

# Функция для нормализации текста
def normalize_text(text):
    translation = str.maketrans("aàáäâbcddefghijklmnoópqrsstuvwxyz", "абцдефгхийклмнñoópqrsstuvwxyz")
    return text.translate(translation)

# Проверка на запрещённые слова
def contains_forbidden_words(text):
    normalized_text = normalize_text(text.lower())
    return any(word in normalized_text for word in FORBIDDEN_WORDS)

# Проверка на наличие обязательных ключевых слов
def contains_allowed_keywords(text):
    normalized_text = normalize_text(text.lower())
    return any(keyword in normalized_text for keyword in ALLOWED_KEYWORDS)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start from {update.message.from_user.username}")
    # Отправляем картинку и приветственное сообщение
    photo_path = 'onyxshopbot.png'  # Указываем путь к картинке
    await update.message.reply_photo(
        photo=open(photo_path, 'rb'),
        caption="Привет! Это бот для публикации объявлений о продаже, покупке и обмене."
    )

# Обработка текстовых сообщений
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    username = update.message.from_user.username or "аноним"
    
    logger.info(f"Received message from {username}: {text}")

    # Проверка на наличие запрещённых слов
    if contains_forbidden_words(text):
        logger.warning(f"Message from {username} contains forbidden words.")
        await update.message.reply_text("❌ Объявление отклонено. Причина: содержит запрещённые слова.")
        return
    
    # Проверка на обязательные ключевые слова
    if not contains_allowed_keywords(text):
        logger.warning(f"Message from {username} does not contain allowed keywords.")
        await update.message.reply_text("❌ Объявление отклонено. Причина: отсутствуют обязательные ключевые слова (например: покупка, продажа, обмен).")
        return

    # Если прошло все проверки
    await update.message.reply_text("✅ Объявление принято и опубликовано.")
    await context.bot.send_message(
        chat_id=TARGET_CHANNEL_ID,
        text=f"Объявление от @{username}:\n{text}"
    )

# Обработка фото
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption or ""
    file_id = update.message.photo[-1].file_id
    username = update.message.from_user.username or "аноним"
    
    logger.info(f"Received photo from {username} with caption: {caption}")

    # Проверка на наличие запрещённых слов
    if contains_forbidden_words(caption):
        logger.warning(f"Photo from {username} contains forbidden words.")
        await update.message.reply_text("❌ Фотообъявление отклонено. Причина: содержит запрещённые слова.")
        return
    
    # Проверка на обязательные ключевые слова
    if not contains_allowed_keywords(caption):
        logger.warning(f"Photo from {username} does not contain allowed keywords.")
        await update.message.reply_text("❌ Фотообъявление отклонено. Причина: отсутствуют обязательные ключевые слова (например: покупка, продажа, обмен).")
        return

    # Если прошло все проверки
    await update.message.reply_text("✅ Фотообъявление принято и опубликовано.")
    await context.bot.send_photo(
        chat_id=TARGET_CHANNEL_ID,
        photo=file_id,
        caption=f"Фотообъявление от @{username}:\n{caption}"
    )

# Запуск Telegram-бота
async def run_telegram_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("Telegram bot started.")
    await application.run_polling()

# Запуск Flask
def start_flask():
    app.run(host='0.0.0.0', port=8080)

# Основная функция для запуска
def main():
    flask_process = multiprocessing.Process(target=start_flask)
    flask_process.start()
    
    # Запускаем Telegram-бота
    asyncio.run(run_telegram_bot())

if __name__ == "__main__":
    main()
