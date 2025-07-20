import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import logging
from flask import Flask, jsonify
import threading

# Загрузка переменных из .env файла
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))
MODERATION_CHAT_ID = int(os.getenv("MODERATION_CHAT_ID"))
REJECTED_CHAT_ID = int(os.getenv("REJECTED_CHAT_ID"))

# Flask для фейкового пинга
app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"status": "Bot is running"})

# Включаем logging для ошибок
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Список разрешённых (обязательных) слов для публикации
ALLOWED_KEYWORDS = [
    "покупка", "продажа", "обмен", "sell", "продаю", "куплю", "trade", "buy", "b",
    "продам", "обменяю", "продажа", "приобрести", "закупка", "обмен", "совершить сделку", 
    "покупаю", "торговля", "обменять", "картридж", "мобильник", "телефон", "фотоаппарат",
    "nft", "цифровой", "сделка", "криптовалюта", "usdt", "dollar", "биткойн", "btc", "eth", 
    "продукция", "товар", "продажа"
]

# Расширенный список запрещённых слов (мат, жаргонизмы, непристойности, мошенничество)
FORBIDDEN_WORDS = [
    "реклама", "подпишись", "подписка", "реферал", "ссылка", "instagram", "youtube", "tiktok", 
    "http", "www", ".com", ".ru", "спам", "порнография", "наркотики", "вагина", "анальный", 
    "суицид", "убийство", "экстремизм", "бесплатно", "кредит", "лохотрон", "обман", "жертва", 
    "мафия", "мошенничество", "пидор", "гей", "лесбиянка", "порн", "видеочат", "сексуальные", 
    "секс", "массажист", "платная подписка", "накрутка", "депозит", "привлечь", "пополнение",
    "водка", "табак", "пиво", "наркота", "путана", "проституция", "деньги в долг", "кредитки",
    "микрозаймы", "псевдонаука", "влияние", "афера", "игры на деньги", "стриптиз", "танцы на пилоне", 
    "игры казино", "игровые автоматы", "лото", "лотереи", "манипуляция", "реклама бизнеса", 
    "махинации", "грузовики", "оружие", "боеприпасы", "интернет-торговля оружием", "пистолет", "пневматика",
    "огнестрельное", "оружие", "кастеты", "порнобизнес", "антибиотики", "стимуляторы", "психотропы",
    "психоделики", "мародерство", "нацизм", "фашизм", "терроризм", "радикальные", "дискриминация",
    "ебать", "пизда", "хуй", "сука", "блядь", "мудак", "пидорас", "заебал", "нахуй", "жопа", "ебаный",
    "блуд", "ебло", "пиздить", "нахера", "погоди", "черти", "сучка", "мразь", "сволочь", "гондон", "урод",
    "псих", "пиздить", "нахера", "погоди", "черти", "сучка", "мразь", "сволочь"
]

# Функция для нормализации текста (замена латиницы на кириллицу)
def normalize_text(text):
    translation = str.maketrans(
        "aàáäâbcddefghijklmnoópqrsstuvwxyz",  # Латиница
        "абцдефгхийклмнñoópqrsstuvwxyz"        # Кириллица
    )
    return text.translate(translation)

# Функция для проверки наличия запрещённых слов
def contains_forbidden_words(text):
    normalized_text = normalize_text(text.lower())
    return any(forbidden_word in normalized_text for forbidden_word in FORBIDDEN_WORDS)

# Функция для проверки, содержит ли текст обязательные ключевые слова
def contains_allowed_keywords(text):
    normalized_text = normalize_text(text.lower())
    return any(keyword in normalized_text for keyword in ALLOWED_KEYWORDS)

# Функция для обработки команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start command from {update.message.from_user.username}")
    # Отправляем картинку и текст в одном сообщении
    photo_path = 'onyxshopbot.png'  # Указываем путь к картинке в той же директории
    await update.message.reply_photo(
        photo=open(photo_path, 'rb'),  # Открываем картинку для отправки
        caption="Привет! Это бот для публикации объявлений о продаже, покупке и обмене в @onyx_sh0p.\n"
                "Для отправки просто пришлите объявление боту."
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

    # Если объявление прошло все проверки, публикуем его
    await update.message.reply_text("✅ Объявление принято и опубликовано.")
    await context.bot.send_message(
        chat_id=TARGET_CHANNEL_ID,
        text=f"Объявление от @{username}:\n{text}"
    )

# Обработка сообщений с фото
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

    # Если объявление прошло все проверки, публикуем его
    await update.message.reply_text("✅ Фотообъявление принято и опубликовано.")
    await context.bot.send_photo(
        chat_id=TARGET_CHANNEL_ID,
        photo=file_id,
        caption=f"Фотообъявление от @{username}:\n{caption}"
    )

# Запуск Telegram бота
async def run_telegram_bot():
    application = ApplicationBuilder().token(TOKEN).build()

    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("Telegram bot started.")
    await application.run_polling()

# Запуск Flask-сервера в отдельном потоке
def start_flask():
    app.run(host='0.0.0.0', port=8080)

def main():
    # Запуск Flask в отдельном потоке
    threading.Thread(target=start_flask, daemon=True).start()
    
    # Запуск Telegram-бота с использованием asyncio.run
    asyncio.run(run_telegram_bot())

if __name__ == '__main__':
    main()
