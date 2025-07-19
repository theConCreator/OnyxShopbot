import os
import threading
from dotenv import load_dotenv
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup, Update)
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask
import logging

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

# Расширенный список запрещённых слов (мат, жаргонизмы, непристойности, мошенничество)
FORBIDDEN_WORDS = [
    "реклама", "подпишись", "подписка", "реферал", "ссылка", "instagram", "youtube", "tiktok", 
    "http", "www", ".com", ".ru", "спам", "порнография", "наркотики", "вагина", "анальный", 
    "суицид", "убийство", "экстремизм", "бесплатно", "кредит", "лохотрон", "обман", "жертва", 
    "мафия", "мошенничество", "пидор", "гей", "лесбиянка", "порн", "видеочат", "сексуальные", 
    "секс", "аноним", "массажист", "платная подписка", "накрутка", "депозит", "привлечь", "пополнение",
    "водка", "табак", "пиво", "наркота", "путана", "проституция", "деньги в долг", "кредитки",
    "микрозаймы", "псевдонаука", "влияние", "афера", "игры на деньги", "стриптиз", "танцы на пилоне", 
    "игры казино", "игровые автоматы", "лото", "лотереи", "манипуляция", "реклама бизнеса", 
    "махинации", "грузовики", "оружие", "боеприпасы", "интернет-торговля оружием", "пистолет", "пневматика",
    "огнестрельное", "оружие", "кастеты", "порнобизнес", "антибиотики", "стимуляторы", "психотропы",
    "психоделики", "мародерство", "нацизм", "фашизм", "терроризм", "радикальные", "дискриминация",
    "ебать", "пизда", "хуй", "сука", "блядь", "мудак", "пидорас", "заебал", "нахуй", "жопа", "ебаный",
    "блуд", "ебло", "пидарас", "соси", "гандон", "урод", "псих", "пиздить", "нахера", "погоди", "черти",
    "сучка", "мразь", "сволочь", "гондон", "питон", "сучий", "петух", "тупая", "ебаный", "выебаться"
]

# Список обязательных слов для публикации объявления
ALLOWED_KEYWORDS = ["покупка", "продажа", "обмен", "sell", "продаю", "куплю", "trade", "buy", "b"]

# Словарь для хранения объявлений на модерации
pending_approvals = {}

# Вспомогательная функция для составления подписи
def build_caption(text: str, username: str, price: str = None):
    user_mention = f"@{username}" if username else "пользователь скрыл имя"
    price_line = f"\nЦена: {price}" if price else ""
    caption = f"""
Объявление
-------------------
{text.strip()}

-------------------
Отправил(а): {user_mention}
"""
    return caption[:1024]  # Ограничение по символам Telegram

# Функция проверки текста на наличие запрещённых слов
def contains_forbidden_words(text: str):
    return any(word in text.lower() for word in FORBIDDEN_WORDS)

# Функция проверки текста на наличие нужных ключевых слов
def contains_allowed_keywords(text: str):
    return any(kw in text.lower() for kw in ALLOWED_KEYWORDS)

# Функция для обработки команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Это бот для публикации объявлений о продаже, покупке и обмене в @onyx_sh0p.\n"
        "Для отправки просто пришлите объявление боту."
    )

# Обработка текстовых сообщений
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        text = update.message.text
        username = update.message.from_user.username or "аноним"
        
        # Добавление цены, если она указана
        price = None
        if "Цена:" in text:
            text, price = text.split("Цена:", 1)
            price = price.strip()

        # Проверка на запрещённые слова
        if contains_forbidden_words(text):
            await update.message.reply_text("❌ Ваше объявление отклонено по причине: содержит запрещённые слова.")
            await context.bot.send_message(
                chat_id=REJECTED_CHAT_ID,
                text=f"Отклонено объявление:\n{text}\nПричина: содержит запрещённые слова."
            )
            return

        # Проверка на наличие обязательных ключевых слов
        if not contains_allowed_keywords(text):
            await update.message.reply_text("❌ Ваше объявление отклонено по причине: отсутствуют ключевые слова (покупка, продажа, обмен и т.п.).")
            await context.bot.send_message(
                chat_id=REJECTED_CHAT_ID,
                text=f"Отклонено объявление:\n{text}\nПричина: отсутствуют ключевые слова."
            )
            return

        # Если объявление прошло все проверки, публикуем его
        await update.message.reply_text("✅ Объявление принято и опубликовано.")
        await context.bot.send_message(
            chat_id=TARGET_CHANNEL_ID,
            text=build_caption(text, username, price),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✍️ Написать продавцу", url=f"https://t.me/{username}")],
                                              [InlineKeyboardButton("📣 Разместить объявление", url="https://t.me/onyxsh0pbot")]])
        )

# Обработка сообщений с фото
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption or ""
    file_id = update.message.photo[-1].file_id
    username = update.message.from_user.username or "аноним"
    
    # Аналогично добавим цену
    price = None
    if "Цена:" in caption:
        caption, price = caption.split("Цена:", 1)
        price = price.strip()

    # Проверка на запрещённые слова
    if contains_forbidden_words(caption):
        await update.message.reply_text("❌ Ваше фотообъявление отклонено по причине: содержит запрещённые слова.")
        await context.bot.send_message(
            chat_id=REJECTED_CHAT_ID,
            text=f"Отклонено фотообъявление:\n{caption}\nПричина: содержит запрещённые слова."
        )
        return

    # Проверка на наличие обязательных ключевых слов
    if not contains_allowed_keywords(caption):
        await update.message.reply_text("❌ Ваше фотообъявление отклонено по причине: отсутствуют ключевые слова (покупка, продажа, обмен и т.п.).")
        await context.bot.send_message(
            chat_id=REJECTED_CHAT_ID,
            text=f"Отклонено фотообъявление:\n{caption}\nПричина: отсутствуют ключевые слова."
        )
        return

    # Если фотообъявление прошло все проверки, публикуем его
    await update.message.reply_text("✅ Ваше фотообъявление принято и опубликовано.")
    await context.bot.send_photo(
        chat_id=TARGET_CHANNEL_ID,
        photo=file_id,
        caption=build_caption(caption, username, price),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✍️ Написать продавцу", url=f"https://t.me/{username}")],
                                          [InlineKeyboardButton("📣 Разместить объявление", url="https://t.me/onyxsh0pbot")]])
    )

# Запуск бота
async def main():
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())


