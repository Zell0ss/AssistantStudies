#%%
import telebot
# from telegram import constants
from openai import OpenAI
import os
import requests
from weather.openmeteo import get_tempt_prompt
from mycalendar.googlecal import get_events
from utils.utils import config, config_file, authorized, classify_text_mimetype, add_authorized_user, upload_document_dropbox
import logging

#%%
import yaml
logging.basicConfig(filename="/home/konnos/data/tests/logs/app.log", filemode='w', format='%(name)s - %(levelname)s - %(message)s')
logging.warning('This will get logged to a file')


BOT_TOKEN = config["telegram_apikey"]
bot = telebot.TeleBot(BOT_TOKEN)

client = OpenAI(api_key = config['openai_apikey'])

messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant"
    }
]
logging.warning("bot started")

openai_org_id = config["openai_org_id"]
openai_api_key = config["openai_apikey"]
headers = {'Authorization': f'Bearer {openai_api_key}'}

# commands are the words that are passed at the beginning of a message preceding by /

# %%
"""
simple test
"""
@bot.message_handler(commands=['start', 'hola'])
def send_welcome(message):
    first_name = message.chat.first_name
    bot.reply_to(message, f"Hola {first_name}, como estás?")

# %%
"""
send the help info
"""
@bot.message_handler(commands=['ayuda', 'help'])
def send_help(message):
    if authorized(message.chat.username, message.chat.id):
        bot.reply_to(message, "Estos son los comandos soportados actualmente")
        bot.send_message(chat_id=message.chat.id, text="*ayuda*: muestra este texto", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text= "*id\_me* o *whoami*: retorna tu usuario y nombre en telegram", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text=  "*chat\_tiempo* o *el\_tiempo*: previsión meteorológica", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text=  "*tiempo*: previsión meteorológica, resumen", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text=  "*imagen*: te devuelve una imagen generada en base al prompt pasado", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text=  "*adduser*: añade el uid del usuario que se le pase a los usuarios autorizados", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text=  "*consumo*: te dirige a la página de consumo de chatgpt", parse_mode="MarkdownV2")

# %%
"""
add user to allowed  ones
"""
@bot.message_handler(commands=['adduser'])
def adduser(message):
    if authorized(message.chat.username, message.chat.id):
        uid = message.text.replace("/adduser", "").strip()
        config = add_authorized_user(uid)
        bot.reply_to(message, f"uid {uid} añadido")
             

# %%
"""
handling files
"""
@bot.message_handler(func=lambda message: classify_text_mimetype(message.document.mime_type) != 'unk' ,
    content_types=['document'])
def command_handle_document(message):
    if authorized(message.chat.username, message.chat.id):
        response = upload_document_dropbox(message)
        bot.send_message(message.chat.id,response)

#%%
"""
retrieve weather -verbose
"""
@bot.message_handler(commands=['chat_tiempo', 'el_tiempo'])
def send_chat_weather(message):
    if authorized(message.chat.username, message.chat.id):
        # bot.reply_to(message, get_tempt_prompt())
        messages.append(
            {
                "role": "user",
                "content": f"A continuación te paso la prevision meteorológica para hoy junto con un refran. \
                     Envíamela formateada agradablemente y con algun comentario a la ropa que se puede llevar \
                     o lo que apetece comer en esta epoca y con la temperatura que hay \
                     si es tipico o no del año, etc y finaliza con el refrán, que también puedes comentar, pero no lo hagas muy largo. {get_tempt_prompt()}"
            },
        )

        chat = client.chat.completions.create(
            messages=messages,
            model="gpt-3.5-turbo"
        )

        reply = chat.choices[0].message
        bot.reply_to(message, reply.content)

#%%
"""
retrieve weather brief
"""
@bot.message_handler(commands=['tiempo'])
def send_weather(message):
    if authorized(message.chat.username, message.chat.id):
        bot.reply_to(message, get_tempt_prompt())

#%%
"""
retrieve tomorrow events
"""
@bot.message_handler(commands=['calendario'])
def send_calendar(message):
    if authorized(message.chat.username, message.chat.id):
        bot.reply_to(message, get_events())

#%%
"""
address to get chatgpt usage
"""        
@bot.message_handler(commands=['consumo'])
def get_consumo(message):
    if authorized(message.chat.username, message.chat.id):
        bot.reply_to(message,  "por favor, visita directamente la página https://platform.openai.com/usage")

# %%
"""
retrieve telegram user and uid 
"""
@bot.message_handler(commands=['id_me', 'whoami'])
def id_user(message):
    username = message.chat.username
    first_name = message.chat.first_name
    user_id = message.chat.id
    bot.reply_to(message, f"id: {user_id}, username: {username}, first_name: {first_name}")

#%%
"""
processes the image
"""
@bot.message_handler(commands=['imagen'])
def imagen(message):
    if authorized(message.chat.username, message.chat.id):
        prompt = message.text.replace("/imagen", "")
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
                )
            image_url = response.data[0].url
            revised_prompt = response.data[0].revised_prompt
        except Exception as exc:
            image_url = "failure"
            revised_prompt = exc

        bot.reply_to(message, f"prompt revisado:{revised_prompt}. url imagen:{image_url}")

# %%
"""
direct question to chatgpt
"""
@bot.message_handler(func=lambda msg: True)
# lambda function always returns true no matter the message 
# so we will be answering back all messages to the user 
# all messages that are not catched in previous decorators
def echo_all(message):
    if authorized(message.chat.username, message.chat.id):
        messages.append(
            {
                "role": "user",
                "content": message.text
            },
        )

        chat = client.chat.completions.create(
            messages=messages,
            model="gpt-3.5-turbo"
        )

        reply = chat.choices[0].message
        bot.reply_to(message, reply.content)


# %%
bot.infinity_polling()

