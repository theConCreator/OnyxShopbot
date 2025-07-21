import os
import logging
import threading
from dotenv import load_dotenv
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# 1) Конфиг
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# 2) Flask для пинга
app = Flask(__name__)
@app.route("/", methods=["GET", "HEAD"])
def alive():
    return "OK", 200

# 3) Логирование
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s  %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# 4) Дебаг‑хендлер, чтобы видеть _всё_
async def debug_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"🔔 Update: {update!r}")

# 5) Упрощённый /start
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"→ /start from @{update.effective_user.username}")
    await update.message.reply_text("Привет! Бот жив и слушает команды.")

# 6) Функция запуска бота
def run_bot():
    application = Application.builder().token(TOKEN).build()

    # ** Debug: ставим первым, чтобы наверняка поймать всё **
    application.add_handler(MessageHandler(filters.ALL, debug_all), group=0)

    # Настоящие хендлеры:
    application.add_handler(CommandHandler("start", start_cmd), group=1)
    # ... сюда можно будет добавлять остальные ваши хендлеры ...

    logger.info("🚀 Запуск Telegram polling…")
    application.run_polling()

# 7) Точка входа
if __name__ == "__main__":
    # Старт Flask в фоне
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080"))),
        daemon=True
    ).start()

    # Старт бота (блокирующий)
    run_bot()
