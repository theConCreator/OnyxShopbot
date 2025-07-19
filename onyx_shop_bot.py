import os
import threading
from dotenv import load_dotenv
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup, Update)
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask
import logging
import re

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
    return "Bot is running."

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Включаем logging для ошибок
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Включаем фейковый Flask для пинга
flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

# Список разрешённых (обязательных) слов для публикации
ALLOWED_KEYWORDS = [
    "покупка", "продажа", "обмен", "sell", "продаю", "куплю", "trade", "buy", "b",
    "продам", "обменяю", "продажа", "приобрести", "закупка", "обмен", "совершить сделку", 
    "покупаю", "торговля", "обменять", "картридж", "мобильник", "телефон", "фотоаппарат",
    "nft", "нфт", "цифровой", "сделка", "криптовалюта", "usdt", "dollar", "биткойн", "btc", "eth", 
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
        "aàáäâbcdçdefghiíjkllmnñoópqrsstúüvwxyz",
        "аàáäâbцдефгиíклмнñoópqrsstúüvwxyz")
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
    await update.message.reply_text(
        "Привет! Это бот для публикации объявлений о продаже, покупке и обмене в @onyx_sh0p.\n"
        "Для отправки просто пришлите объявление боту."
    )

# Обработка текстовых сообщений
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    username = update.message.from_user.username or "аноним"
    
    # Проверка на наличие запрещённых слов
    if contains_forbidden_words(text):
        await update.message.reply_text("❌ Объявление отклонено. Причина: содержит запрещённые слова.")
        return
    
    # Проверка на обязательные ключевые слова
    if not contains_allowed_keywords(text):
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
    
    # Проверка на наличие запрещённых слов
    if contains_forbidden_words(caption):
        await update.message.reply_text("❌ Фотообъявление отклонено. Причина: содержит запрещённые слова.")
        return
    
    # Проверка на обязательные ключевые слова
    if not contains_allowed_keywords(caption):
        await update.message.reply_text("❌ Фотообъявление отклонено. Причина: отсутствуют обязательные ключевые слова (например: покупка, продажа, обмен).")
        return

    # Если объявление прошло все проверки, публикуем его
    await update.message.reply_text("✅ Фотообъявление принято и опубликовано.")
    await context.bot.send_photo(
        chat_id=TARGET_CHANNEL_ID,
        photo=file_id,
        caption=f"Фотообъявление от @{username}:\n{caption}"
    )

# Обработка модерации
async def handle_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, ad_id = query.data.split("_")
    
    ad = pending_approvals.pop(int(ad_id), None)
    if ad is None:
        await query.edit_message_text("❌ Объявление уже обработано.")
        return

    if action == "approve":
        if ad["type"] == "photo":
            await context.bot.send_photo(
                chat_id=TARGET_CHANNEL_ID,
                photo=ad["file_id"],
                caption=f"Фотообъявление от @{ad['username']}:\n{ad['text']}"
            )
        else:
            await context.bot.send_message(
                chat_id=TARGET_CHANNEL_ID,
                text=f"Объявление от @{ad['username']}:\n{ad['text']}"
            )
        await query.edit_message_text("✅ Объявление одобрено и опубликовано.")
        await context.bot.send_message(
            chat_id=ad["username"],
            text="Ваше объявление было успешно выложено!"
        )
    elif action == "reject":
        await query.edit_message_text("❌ Объявление отклонено.")
        await context.bot.send_message(REJECTED_CHAT_ID, f"Отклонено объявление:\n{ad['text']}")
        await context.bot.send_message(
            chat_id=ad["username"],
            text="Ваше объявление отклонено по причине: несоответствие правилам."
        )

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_moderation))

    application.run_polling()

