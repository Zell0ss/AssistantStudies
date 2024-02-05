#%%
import telebot
# from telegram import constants
from openai import OpenAI
import os
import json
import requests
import datetime
from weather.openmeteo import get_tempt_prompt
from mycalendar.googlecal import get_events

#%%
import yaml

# Intenta cargar el archivo config.yaml desde el mismo directorio
try:
    ruta_fichero = os.path.abspath(__file__)
    config_file = ruta_fichero.replace("sebastian_bot.py", "config.yaml")
    with open(config_file, 'r') as archivo_config:
        config = yaml.safe_load(archivo_config)
except FileNotFoundError:
    print("El archivo config.yaml no se encuentra en el directorio.")
    raise
except yaml.YAMLError as e:
    print(f"Error al cargar el archivo config.yaml: {e}")
    raise


BOT_TOKEN = config["telegram_apikey"]
bot = telebot.TeleBot(BOT_TOKEN)

client = OpenAI(api_key = config['openai_apikey'])

messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant"
    }
]

def authorized(username, userid):
    if  username in config["authorized_users"] or userid in config["authorized_ids"]:
        return True
    return False

def classify_text_mimetype(mime_type):
    if mime_type == 'application/pdf':
        return "PDF"
    elif mime_type == 'application/msword' or mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        return "DOC"
    elif mime_type == 'text/plain':
        return "TXT"
    else:
        return "OTHER"
    
def parse_for_markdown(text:str):
    return None

openai_org_id = config["openai_org_id"]
openai_api_key = config["openai_apikey"]
headers = {'Authorization': f'Bearer {openai_api_key}'}


# %%
# commands are all words that are passed preceding by /
@bot.message_handler(commands=['start', 'hola'])
def send_welcome(message):
    first_name = message.chat.first_name
    bot.reply_to(message, f"Hola {first_name}, como estás?")

# %%
@bot.message_handler(commands=['ayuda', 'help'])
def send_help(message):
    if authorized(message.chat.username, message.chat.id):
        bot.reply_to(message, "Estos son los comandos soportados actualmente")
        bot.send_message(chat_id=message.chat.id, text="*ayuda*: muestra este texto", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text= "*id\_me* o *whoami*: retorna tu usuario y nombre en telegram", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text=  "*chat\_tiempo* o *el\_tiempo*: previsión meteorológica", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text=  "*tiempo*: previsión meteorológica, resumen", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text=  "*imagen*: te devuelve una imagen generada en base al prompt pasado", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text=  "*consumo*: te dirige a la página de consumo de chatgpt", parse_mode="MarkdownV2")

# %%
#handling documents
@bot.message_handler(func=lambda message: classify_text_mimetype(message.document.mime_type) != 'OTHER' ,
    content_types=['document'])
def command_handle_document(message):
    # message.document
    bot.send_message(message.chat.id, 'Document received, sir!')

#%%
@bot.message_handler(commands=['chat_tiempo', 'el_tiempo'])
def send_chat_weather(message):
    if authorized(message.chat.username, message.chat.id):
        # bot.reply_to(message, get_tempt_prompt())
        messages.append(
            {
                "role": "user",
                "content": f"A continuación te paso la prevision meteorológica para hoy junto con un refran. \
                     Envíamela formateada agradablemente y con algun comentario a la ropa que se puede llevar \
                     o lo que apetece comer en eswta epoca y con la temperatura que hay \
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
@bot.message_handler(commands=['tiempo'])
def send_weather(message):
    if authorized(message.chat.username, message.chat.id):
        bot.reply_to(message, get_tempt_prompt())

#%%
@bot.message_handler(commands=['calendario'])
def send_calendar(message):
    if authorized(message.chat.username, message.chat.id):
        bot.reply_to(message, get_events())


#%%        
@bot.message_handler(commands=['consumo'])
def get_consumo(message):
    if authorized(message.chat.username, message.chat.id):
        bot.reply_to(message,  "por favor, visita directamente la página https://platform.openai.com/usage")
# %%
@bot.message_handler(commands=['id_me', 'whoami'])
def id_user(message):
    username = message.chat.username
    first_name = message.chat.first_name
    user_id = message.chat.id
    bot.reply_to(message, f"id: {user_id}, username: {username}, first_name: {first_name}")

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

