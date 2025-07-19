import os
import logging
import re
import html
import unicodedata
from flask import Flask
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from langdetect import detect

# Загрузка env-переменных
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MODERATION_CHAT_ID = int(os.getenv("MODERATION_CHAT_ID"))
REJECTED_CHAT_ID = int(os.getenv("REJECTED_CHAT_ID"))
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))

# Flask сервер для Render пинга
app = Flask(__name__)

@app.route('/')
def ping():
    return "I'm alive", 200

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Хештеги
KEYWORDS = {
    "sell": ["продажа", "продаю", "селл", "sell"],
    "buy": ["покупка", "куплю", "ищу", "бай", "buy"],
    "exchange": ["обмен", "обмениваю", "меняю", "exchange"],
    "category": [
        "подарки", "nft", "юзер", "username", "аккаунт", "звезды", "чат", "канал",
        "доллары", "тон", "usdt", "ton", "rub", "crypto", "крипта", "монеты"
    ]
}

BLOCKED_WORDS = ["https://", "http://", "t.me/joinchat", "переходи", "подписывайся", "реклама", "зарегистрируйся"]

ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZабвгдеёжзийклмнопрстуфхцчшщъыьэюя"
                    "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ1234567890 $+×÷/<[]>';@()¥~》¤£•♡.,!?%:#\"")

# Для хранения времени последней публикации
from datetime import datetime, timedelta
last_post_time = datetime.min

# === Утилиты ===

def normalize_text(text):
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = html.unescape(text)
    return text.lower()

def extract_hashtags(text):
    tags = set()
    lower = normalize_text(text)
    for tag, words in KEYWORDS.items():
        if any(word in lower for word in words):
            tags.add(tag)
    return tags

def has_blocked_content(text):
    lower = normalize_text(text)
    return any(bad in lower for bad in BLOCKED_WORDS)

def contains_illegal_chars(text):
    return any(c not in ALLOWED_CHARS for c in text)

def is_text_allowed(text):
    try:
        lang = detect(text)
        return lang in ["ru", "en"]
    except:
        return False

# === Обработка сообщений ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь мне объявление — текст (до 100 символов) и одну картинку (опционально).\n"
                                    "Объявления: только покупка, продажа или обмен NFT и сопутствующих товаров.\n"
                                    "🚫 Реклама и ссылки запрещены.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_post_time
    msg = update.message

    text = msg.text or ""
    photo = msg.photo[-1].file_id if msg.photo else None
    user = msg.from_user
    username = user.username or user.first_name

    normalized = normalize_text(text)
    hashtags = extract_hashtags(text)

    # Проверки
    reasons = []
    if len(text) > 100:
        reasons.append("🔴 Текст длиннее 100 символов.")
    if has_blocked_content(text):
        reasons.append("🔴 Обнаружено запрещённое слово или ссылка.")
    if contains_illegal_chars(text):
        reasons.append("🔴 Используются подозрительные символы.")
    if not is_text_allowed(text):
        reasons.append("🔴 Разрешён только русский или английский язык.")
    if len(hashtags) == 0:
        reasons.append("🔴 Не найдено ключевых слов (продажа, покупка, обмен и т.д.).")

    # Формируем сообщение
    tags_text = ' '.join(f"#{tag}" for tag in hashtags)
    final_text = f"{tags_text}\n\n📢 Объявление\n\n"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Написать продавцу", url=f"tg://user?id={user.id}")]
    ])

    final_text += f""

    # Решение: auto, moderate, reject
    if reasons:
        reason_text = "\n".join(reasons)
        await context.bot.send_message(chat_id=REJECTED_CHAT_ID,
                                       text=f"❌ Отклонено объявление от @{username}:\n\n{text}\n\nПричины:\n{reason_text}")
        await msg.reply_text("Ваше объявление не прошло проверку:\n" + reason_text)
        return

    if datetime.now() - last_post_time < timedelta(hours=1):
        # Слишком часто — на модерацию
        await context.bot.send_message(chat_id=MODERATION_CHAT_ID,
                                       text=f"⚠️ Подозрительное объявление от @{username}:\n\n{text}")
        await msg.reply_text("Ваше объявление отправлено на модерацию.")
        return

    # Успешная публикация
    last_post_time = datetime.now()
    final_text += f"👤 @{username}"

    if photo:
        await context.bot.send_photo(chat_id=TARGET_CHANNEL_ID, photo=photo,
                                     caption=final_text, reply_markup=keyboard)
    else:
        await context.bot.send_message(chat_id=TARGET_CHANNEL_ID, text=final_text, reply_markup=keyboard)

    await msg.reply_text("✅ Объявление опубликовано!")

# === Запуск ===

def main():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))

    # Запуск телеграм-бота
    application.run_polling()

if __name__ == "__main__":
    from threading import Thread
    Thread(target=main).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
