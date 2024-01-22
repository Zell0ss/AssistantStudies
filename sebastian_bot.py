#%%
import telebot
from openai import OpenAI
import os
import json
import requests
import datetime

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


openai_org_id = config["openai_org_id"]
openai_api_key = config["openai_apikey"]
headers = {'Authorization': f'Bearer {openai_api_key}'}


# url = 'https://api.openai.com/v1/usage'

# hoy = datetime.date.today()
# primer_dia = datetime.date(hoy.year, 1, 1)
# delta = datetime.timedelta(days=1)
# while primer_dia <= hoy:
#     params = {'date': primer_dia.strftime('%Y-%m-%d')}
#     primer_dia += delta
#     response = requests.get(url, headers=headers, params=params)
#     usage_data = response.json()


# curl -s "https://api.openai.com/dashboard/billing/usage?end_date=2024-12-31&start_date=2024-01-01" \
# -H "Authorization: Bearer {openai_api_key}" \
# -H "OpenAI-Organization: {openai_org_id}"  

# %%
# commands are all words that are passed preceding by /
@bot.message_handler(commands=['start', 'hola'])
def send_welcome(message):
    first_name = message.chat.first_name
    bot.reply_to(message, f"Hola {first_name}, como estás?")

@bot.message_handler(commands=['consumo'])
def send_welcome(message):
    if authorized(message.chat.username, message.chat.id):
        
        bot.reply_to(message,  "por favor, visita directamente la página https://platform.openai.com/usage")

@bot.message_handler(commands=['id_me', 'whoami'])
def id_user(message):
    username = message.chat.username
    first_name = message.chat.first_name
    user_id = message.chat.id
    bot.reply_to(message, f"id: {user_id}, username: {username}, first_name: {first_name}")

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

#%%


# %%
bot.infinity_polling()

