import logging
import json
import subprocess
import time

import requests
from telegram import (Update,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove, ChatAction, MessageEntity)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    MessageHandler,
    Filters,
    ConversationHandler,
)
import export_to_telegraph

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def start(update: Update, context: CallbackContext):
    update.message.reply_text('Greetings! Welcome to Article Reader Bot')


def unshorten_url(url):
    return requests.get(url).url


def get_telegraph_url(update: Update, context: CallbackContext):
    url = update.message.text
    # url = unshorten_url(url) if "link.medium.com" in url else url  # unshorten medium.com urls
    # print(url)


    m_id = update.message.reply_text('Please wait while I fetch the article...', quote=True).message_id
    telegraph_url = export_to_telegraph.export(url, force=True)
    context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=m_id, text=telegraph_url)


def main():
    with open('config.json') as config_file:
        config = json.load(config_file)
    updater = Updater(token=config['tg_token'], use_context=True)
    dispatcher = updater.dispatcher

    start_handler = CommandHandler('start', start)
    telegraph_handler = MessageHandler(Filters.text & (Filters.entity('url') | Filters.entity(MessageEntity.TEXT_LINK)),
                                       get_telegraph_url)

    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(telegraph_handler)
    updater.start_polling()


if __name__ == '__main__':
    main()
