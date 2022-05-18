import logging
import json
import subprocess
import time
from telegram import (Update,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove, ChatAction)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    MessageHandler,
    Filters,
    ConversationHandler,
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def start(update: Update, context: CallbackContext):
    update.message.reply_text('Greetings! Welcome to Article Reader Bot')


def main():
    with open('config.json') as config_file:
        config = json.load(config_file)
    updater = Updater(token=config['tg_token'], use_context=True)
    dispatcher = updater.dispatcher

    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)
    updater.start_polling()


if __name__ == '__main__':
    main()
