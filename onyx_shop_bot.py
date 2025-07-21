import logging

# Создаем логер
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Настроим хендлер для отправки логов в Telegram
class TelegramLogHandler(logging.Handler):
    def __init__(self, bot, chat_id):
        super().__init__()
        self.bot = bot
        self.chat_id = chat_id

    def emit(self, record):
        log_message = self.format(record)
        self.bot.send_message(chat_id=self.chat_id, text=log_message)

# Используем этот обработчик для отправки логов в Telegram
def setup_logger(bot, chat_id):
    handler = TelegramLogHandler(bot, chat_id)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Пример использования
# setup_logger(bot_instance, 'your_chat_id')

