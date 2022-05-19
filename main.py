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
import mutagen
from mutagen.easyid3 import EasyID3
import tldextract
import domain_list

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

READ, LISTEN = range(2)

article_of_user = {}
last_bot_message = {}

with open('config.json') as config_file:
    config = json.load(config_file)
export_to_telegraph.token = config['telegraph_token']
speech_config = speechsdk.SpeechConfig(subscription=config['subscription'], region=config['region'])
speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3)


def start(update: Update, context: CallbackContext):
    last_bot_message[update.effective_chat.id] = update.message.reply_text(text="**Send me any article url: **",
                                                                           parse_mode="Markdown").message_id
    return READ


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


def read(update: Update, context: CallbackContext):
    if update.effective_chat.id in last_bot_message:
        context.bot.delete_message(chat_id=update.effective_chat.id,
                                   message_id=last_bot_message[update.effective_chat.id])
        last_bot_message.pop(update.effective_chat.id, None)

    url = update.message.text
    m_id = update.message.reply_text('Fetching the article...', reply_markup=ReplyKeyboardRemove()).message_id

    domain, telegraph_url = instant_view(url)
    article_of_user[update.effective_chat.id] = [domain, telegraph_url]

    context.bot.delete_message(chat_id=update.effective_chat.id, message_id=m_id)
    update.message.reply_text(text=telegraph_url)

    last_bot_message[update.effective_chat.id] = update.message.reply_text(text="Want to Listen to it?",
                                                                           reply_markup=ReplyKeyboardMarkup(
                                                                               keyboard=[["Yes", "No"]],
                                                                               one_time_keyboard=True,
                                                                               resize_keyboard=True)).message_id
    return LISTEN


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


def listen(update: Update, context: CallbackContext):
    if update.effective_chat.id in last_bot_message:
        context.bot.delete_message(chat_id=update.effective_chat.id,
                                   message_id=last_bot_message[update.effective_chat.id])
        last_bot_message.pop(update.effective_chat.id, None)
    context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    if update.message.text == "No":
        m_id = update.message.reply_text(text="Alight!", reply_markup=ReplyKeyboardRemove()).message_id
        time.sleep(1)
        context.bot.delete_message(chat_id=update.effective_chat.id, message_id=m_id)
        return ConversationHandler.END

    m_id = update.message.reply_text('Converting the article to speech...',
                                     reply_markup=ReplyKeyboardRemove()).message_id

    author, url = article_of_user[update.effective_chat.id]
    title, text = extract_text(url)
    get_text2speech(title, text)

    filename = f"{title}.mp3"
    try:
        meta = EasyID3(filename)
    except mutagen.id3.ID3NoHeaderError:
        meta = mutagen.File(filename, easy=True)
        meta.add_tags()
    meta['title'] = title
    meta['artist'] = author.title()
    meta.save(filename, v2_version=3)

    context.bot.delete_message(chat_id=update.effective_chat.id, message_id=m_id)
    context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_AUDIO)
    context.bot.send_audio(chat_id=update.effective_chat.id, audio=open(filename, 'rb'), timeout=100,
                           caption=title, reply_markup=ReplyKeyboardRemove())
    os.remove(filename)
    return ConversationHandler.END


def exit(update: Update, context: CallbackContext):
    return ConversationHandler.END


def main():
    updater = Updater(token=config['tg_token'], use_context=True)
    dispatcher = updater.dispatcher

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start),
                      MessageHandler(Filters.text & (Filters.entity('url') | Filters.entity(MessageEntity.TEXT_LINK)),
                                     read)],
        states={
            READ: [MessageHandler(Filters.text & (Filters.entity('url') | Filters.entity(MessageEntity.TEXT_LINK)),
                                  read)],
            LISTEN: [MessageHandler(Filters.regex("Yes|No"), listen)],
        },
        fallbacks=[CommandHandler('start', start)],
        run_async=True
    )

    dispatcher.add_handler(conversation_handler)
    updater.start_polling()


if __name__ == '__main__':
    main()
