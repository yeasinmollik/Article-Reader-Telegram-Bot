import logging
import json
import subprocess
import time
import re
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
import azure.cognitiveservices.speech as speechsdk

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

with open('config.json') as config_file:
    config = json.load(config_file)
export_to_telegraph.token = config['telegraph_token']
speech_config = speechsdk.SpeechConfig(subscription=config['subscription'], region=config['region'])
speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)


def start(update: Update, context: CallbackContext):
    update.message.reply_text('Greetings! Welcome to Article Reader Bot')


def unshorten_url(url):
    return requests.get(url).url


def instant_view(url):
    return "https://" + export_to_telegraph.export(url, force=True, noSourceLink=True)


def get_telegraph_url(update: Update, context: CallbackContext):
    url = update.message.text

    # unshorten link.medium.com urls
    if "link.medium.com" in url:
        url = unshorten_url(url)

    # bypassing paywalls for medium articles
    if "medium.com" in url:
        url = re.sub(r'^.*?.com', 'https://scribe.rip', url)

    m_id = update.message.reply_text('Fetching the article...').message_id
    # context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    telegraph_url = instant_view(url)
    context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=m_id, text=telegraph_url)


def get_text2speech(text, title):
    audio_config = speechsdk.audio.AudioOutputConfig(filename=f"{title}.mp3")
    speech_config.speech_synthesis_voice_name = 'en-US-ChristopherNeural'
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    speech_synthesis_result = speech_synthesizer.speak_text_async(text).get()


def text2speech(update: Update, context: CallbackContext, title):
    url = update.message.text


def main():
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
