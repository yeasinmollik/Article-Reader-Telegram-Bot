import logging
import json
import os
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
from newspaper import Article
from mutagen.id3 import ID3, ID3NoHeaderError
import tldextract
import domain_list

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

LINK, CHOOSE, READ, LISTEN = range(4)

link_of_user = {}

with open('config.json') as config_file:
    config = json.load(config_file)
export_to_telegraph.token = config['telegraph_token']
speech_config = speechsdk.SpeechConfig(subscription=config['subscription'], region=config['region'])
speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)


def start(update: Update, context: CallbackContext):
    update.message.reply_text(text="**Send me any article url: **", parse_mode="Markdown")
    return LINK


def unshorten_url(url):
    return requests.get(url).url


def instant_view(url):
    # unshorten link.medium.com urls
    if "link.medium.com" in url:
        url = unshorten_url(url)

    # bypassing paywalls for medium articles
    domain = tldextract.extract(url).domain
    if domain in domain_list.domains:
        url = re.sub(r'^.*?.com', 'https://scribe.rip', url)

    return [domain, "https://" + export_to_telegraph.export(url, force=True)]


def get_telegraph_url(update: Update, context: CallbackContext):
    url = link_of_user[update.effective_chat.id]

    m_id = update.message.reply_text('Fetching the article...', reply_markup=ReplyKeyboardRemove()).message_id
    telegraph_url = instant_view(url)[1]

    context.bot.delete_message(chat_id=update.effective_chat.id, message_id=m_id)
    update.message.reply_text(text=telegraph_url)
    return ConversationHandler.END


def get_text2speech(title, text):
    audio_config = speechsdk.audio.AudioOutputConfig(filename=f"{title}.mp3")
    speech_config.speech_synthesis_voice_name = 'en-GB-SoniaNeural'
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    speech_synthesizer.speak_text_async(text).get()


def extract_text(url):
    article = Article(url)
    article.download()
    article.parse()
    return [article.title, article.text]


def text2speech(update: Update, context: CallbackContext):
    m_id = update.message.reply_text('Converting the article to speech...',
                                     reply_markup=ReplyKeyboardRemove()).message_id
    url = link_of_user[update.effective_chat.id]
    domain, telegraph_url = instant_view(url)
    title, text = extract_text(telegraph_url)
    get_text2speech(title, text)

    try:
        tags = ID3(f"{title}.mp3")
    except ID3NoHeaderError:
        tags = ID3()
    tags["title"] = title
    tags["artist"] = domain
    tags.save(f"{title}.mp3")

    context.bot.delete_message(chat_id=update.effective_chat.id, message_id=m_id)
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_AUDIO)
    context.bot.send_audio(chat_id=update.effective_chat.id, audio=open(f"{title}.mp3", 'rb'), timeout=100,
                           caption=title, reply_markup=ReplyKeyboardRemove())

    os.remove(f"{title}.mp3")
    return ConversationHandler.END


def choose_an_option(update: Update, context: CallbackContext):
    if update.message.text == "Read Article":
        return READ
    elif update.message.text == "Listen to Article":
        return LISTEN
    elif update.message.text == "Exit":
        return ConversationHandler.END


def handle_url(update: Update, context: CallbackContext):
    url = update.message.text
    link_of_user[update.effective_chat.id] = url

    keyword = [["Read Article"], ["Listen to Article"], ["Exit"]]

    update.message.reply_text(text="Choose an option: ",
                              reply_markup=ReplyKeyboardMarkup(keyboard=keyword, one_time_keyboard=True,
                                                               resize_keyboard=True))
    return CHOOSE


def main():
    updater = Updater(token=config['tg_token'], use_context=True)
    dispatcher = updater.dispatcher

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start),
                      MessageHandler(Filters.text & (Filters.entity('url') | Filters.entity(MessageEntity.TEXT_LINK)),
                                     handle_url)],
        states={
            LINK: [MessageHandler(Filters.text & (Filters.entity('url') | Filters.entity(MessageEntity.TEXT_LINK)),
                                  handle_url)],
            CHOOSE: [MessageHandler(Filters.text("Read Article"), get_telegraph_url),
                     MessageHandler(Filters.text("Listen to Article"), text2speech)]
        },
        fallbacks=[CommandHandler('start', start)],
        run_async=True
    )

    dispatcher.add_handler(conversation_handler)
    updater.start_polling()


if __name__ == '__main__':
    main()
