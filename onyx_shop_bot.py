import os
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

# Загрузка переменных окружения
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

# Запуск Flask сервера в отдельном потоке
def start_flask_server():
    app.run(host="0.0.0.0", port=5000)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Структуры данных для хранения заявок на модерацию
pending_approvals = {}

# Функция для создания кнопок модерации
def moderation_buttons(ad_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Approve", callback_data=f"approve_{ad_id}")],
        [InlineKeyboardButton("Reject", callback_data=f"reject_{ad_id}")]
    ])

# Функция для создания кнопки "Написать отправителю"
def contact_seller_button(username):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Написать отправителю", url=f"t.me/{username}")]
    ])

# Обработка команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я бот для публикации объявлений о продаже, покупке и обмене NFT.")

# Проверка объявления
def is_valid_ad(message_text):
    # Простейшая проверка: длина сообщения < 100 символов и наличие ключевых слов
    keywords = ['продажа', 'покупка', 'обмен', 'nft', 'крипта']
    if any(keyword in message_text.lower() for keyword in keywords) and len(message_text) <= 100:
        return True
    return False

# Обработка текстовых сообщений
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_username = update.message.from_user.username

    if is_valid_ad(user_message):
        # Если объявление прошло проверку, отправляем в канал с кнопкой "Написать отправителю"
        await update.message.reply_text(f"Ваше объявление принято: {user_message}")
        await context.bot.send_message(
            TARGET_CHANNEL_ID, 
            f"Объявление:\n{user_message}\n\nОпубликовал(а): @{update.message.from_user.username}",
            reply_markup=contact_seller_button(user_username)  # Добавляем кнопку с ссылкой на отправителя
        )
    else:
        # Если не прошло проверку, отправляем на модерацию
        ad_id = update.message.message_id
        pending_approvals[ad_id] = update.message.text
        await context.bot.send_message(
            MODERATION_CHAT_ID, 
            f"Новое объявление на модерацию:\n{user_message}\n\nИспользуйте кнопки ниже для принятия решения.",
            reply_markup=moderation_buttons(ad_id)
        )
        await update.message.reply_text("Ваше объявление отправлено на модерацию.")

# Обработка фото
async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем фото
    user_photo = update.message.photo[-1].file_id  # Получаем ID самого качественного фото (последний элемент в списке)
    user_caption = update.message.caption  # Получаем описание фотографии
    user_username = update.message.from_user.username  # Получаем имя пользователя

    # Если фото не имеет подписи, используем заглушку для проверки
    if user_caption is None:
        user_caption = ""

    # Проверяем, является ли описание (или его отсутствие) валидным
    if is_valid_ad(user_caption):
        # Если описание фотографии прошла проверку
        await update.message.reply_text(f"Ваше объявление с фото принято.")
        await context.bot.send_media_group(
            TARGET_CHANNEL_ID, 
            [InputMediaPhoto(user_photo, caption=user_caption)],
            reply_markup=contact_seller_button(user_username)  # Добавляем кнопку с ссылкой на отправителя
        )
    else:
        # Если описание фотографии не прошло проверку, отправляем на модерацию
        ad_id = update.message.message_id
        pending_approvals[ad_id] = user_caption or "Без описания"
        await context.bot.send_message(
            MODERATION_CHAT_ID, 
            f"Новое объявление с фото на модерацию:\n{user_caption}\n\nИспользуйте кнопки ниже для принятия решения.",
            reply_markup=moderation_buttons(ad_id)
        )
        await update.message.reply_text("Ваше объявление с фото отправлено на модерацию.")

# Обработка нажатий на кнопки модерации
async def handle_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    ad_id = query.data.split("_")[1]  # Извлекаем ID объявления
    message = pending_approvals.pop(int(ad_id), None)

    if message:
        if query.data.startswith("approve"):
            # Публикуем в канал
            await context.bot.send_message(TARGET_CHANNEL_ID, f"Объявление:\n{message}")
            await query.answer("Объявление одобрено и опубликовано в канал.")
            await context.bot.send_message(MODERATION_CHAT_ID, "Объявление опубликовано.")
        elif query.data.startswith("reject"):
            # Отклоняем и уведомляем пользователя
            await context.bot.send_message(REJECTED_CHAT_ID, f"Объявление отклонено: {message}")
            await query.answer("Объявление отклонено.")
            await context.bot.send_message(MODERATION_CHAT_ID, "Объявление отклонено.")
    else:
        await query.answer("Ошибка: Объявление не найдено.")

# Инициализация бота
def main():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))  # Добавляем обработку фото
    application.add_handler(CallbackQueryHandler(handle_moderation))

    # Запуск бота
    application.run_polling()

# Запуск Flask и бота в отдельных потоках
if __name__ == "__main__":
    thread = Thread(target=start_flask_server)
    thread.start()

    main()


