#%%
import telebot
# from telegram import constants
from openai import OpenAI
import os
import requests
from weather.openmeteo import get_tempt_prompt
from mycalendar.googlecal import get_events
from utils.utils import config, authorized, classify_text_mimetype, add_authorized_user, upload_document_dropbox, restart_service,stop_service,parse_nota_cata
import logging

#%%
import yaml
logging.basicConfig(filename="/home/konnos/data/tests/logs/app.log", filemode='w', format='%(name)s - %(levelname)s - %(message)s')
logging.warning('This will get logged to a file')


BOT_TOKEN = config["telegram_apikey"]
bot = telebot.TeleBot(BOT_TOKEN)

client = OpenAI(api_key = config['openai_apikey'])
GPT4 = "gpt-4o"
GPT3 = "gpt-3.5-turbo"
CURRENT_GPT_MODEL = GPT4
DALLE3 = "dall-e-3"
CURRENT_DALLE_MODEL = DALLE3
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
managing service
"""
@bot.message_handler(commands=['restart'])
def restart_bot(message):
    if authorized(message.chat.username, message.chat.id):
        bot.reply_to(message, f"restarting service")
        restart_service()

@bot.message_handler(commands=['restart'])
def stop_bot(message):
    if authorized(message.chat.username, message.chat.id):
        bot.reply_to(message, f"stopping service. must be manually restarted")
        stop_service()

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
        bot.send_message(chat_id=message.chat.id, text=  "*plantilla*: devuelve la plantilla para una nota de cata", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text=  "*presentacion*: te hace la presentación para las diferentes plataformas sociales del tema que le digas", parse_mode="MarkdownV2")
        bot.send_message(chat_id=message.chat.id, text=  "*nota\_cata*: te genera una nota de cata mas redactada a partir de la plantilla", parse_mode="MarkdownV2")

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
def get_id_user(message):
    username = message.chat.username
    first_name = message.chat.first_name
    user_id = message.chat.id
    bot.reply_to(message, f"id: {user_id}, username: {username}, first_name: {first_name}")
# %%
"""
add user to allowed ones
"""
@bot.message_handler(commands=['adduser'])
def add_user(message):
    if authorized(message.chat.username, message.chat.id):
        uid = message.text.replace("/adduser", "").strip()
        config = add_authorized_user(uid)
        bot.reply_to(message, f"uid {uid} añadido")
             

# %%
"""
handling files to dropbox
"""
@bot.message_handler(func=lambda message: classify_text_mimetype(message.document.mime_type) != 'unk' ,
    content_types=['document'])
def command_handle_document(message):
    if authorized(message.chat.username, message.chat.id):
        response = upload_document_dropbox(message)
        bot.send_message(message.chat.id,response)

#%%
"""
retrieve weather -verbose and brief
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
            model=CURRENT_GPT_MODEL
        )

        reply = chat.choices[0].message
        bot.reply_to(message, reply.content)

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
processes the image
"""
@bot.message_handler(commands=['imagen'])
def imagen(message):
    if authorized(message.chat.username, message.chat.id):
        prompt = message.text.replace("/imagen", "")
        try:
            response = client.images.generate(
                model=CURRENT_DALLE_MODEL,
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
#%%
"""
winebot entries
"""
@bot.message_handler(commands=['plantilla'])
def send_plantilla(message):
    if authorized(message.chat.username, message.chat.id):
        bot.reply_to(message, "Estos son los campos necesarios para la nota de cata")
        bot.send_message(chat_id=message.chat.id, text="""
*Nombre del vino*: 
*Bodega*: 
*Región*:
*Uvas*: 
*Nota de cata visual*:
*Nota de cata olfativa*: 
*Nota de cata gustativa*: 
*Puntuación personal \(acidez, tanicidad, final, fruta, madera, cuerpo\)*: """, parse_mode="MarkdownV2")


@bot.message_handler(commands=['presentacion'])
def get_presentacion(message):
    if authorized(message.chat.username, message.chat.id):
        messages.append(
            {
                "role": "user",
                "content": f"Preparame una pequeña presentación para twitter, Instagram y Tumblr del artículo que he publicado en https://gotasdivinas.blogspot.com/ sobre {message.text}"
            },
        )

        chat = client.chat.completions.create(
            messages=messages,
            model=CURRENT_GPT_MODEL
        )

        reply = chat.choices[0].message
        bot.reply_to(message, reply.content)

@bot.message_handler(commands=['resumen'])
def get_resumen(message):
    if authorized(message.chat.username, message.chat.id):
        messages.append(
            {
                "role": "user",
                "content": f"""Preparame una pequeña presentación para twitter, Instagram y Tumblr del artículo que he publicado en https://gotasdivinas.blogspot.com/. 
                La presentación ha de ir en primera persona, como si te lo contase yo y tener un lenguaje cercano. No debe de tratar de tu al  
                El artículo trata sobre {message.text}"""
            },
        )

        chat = client.chat.completions.create(
            messages=messages,
            model=CURRENT_GPT_MODEL
        )

        reply = chat.choices[0].message
        bot.reply_to(message, reply.content)

@bot.message_handler(commands=['nota_cata'])
def get_nota_cata(message):
    if authorized(message.chat.username, message.chat.id):
        nota_cata_str = message.text
        nota_cata_dict = parse_nota_cata(nota_cata_str)
        if nota_cata_dict.get("Bodega"):
            messages.append(
                {
                    "role": "user",
                    "content": f"¿Que me puedes decir de la bodega{nota_cata_dict.get('Bodega')}?"
                },
            )
            chat = client.chat.completions.create(
                messages=messages,
                model=CURRENT_GPT_MODEL
            )

            reply = chat.choices[0].message
            bot.send_message(chat_id=message.chat.id, text= reply.content)
        
        messages.append(
                {
                    "role": "user",
                    "content": f"Hazme una nota de cata basada en esta: {nota_cata_str}?"
                },
        )
        chat = client.chat.completions.create(
            messages=messages,
            model=CURRENT_GPT_MODEL
        )

        reply = chat.choices[0].message
        bot.send_message(chat_id=message.chat.id, text= reply.content)


# %%
"""
direct question to chatgpt 4
"""
@bot.message_handler(commands=['4'])
def echo_to_four(message):
    if authorized(message.chat.username, message.chat.id):
        messages.append(
            {
                "role": "user",
                "content": message.text
            },
        )

        chat = client.chat.completions.create(
            messages=messages,
            model=GPT4
        )

        reply = chat.choices[0].message
        bot.reply_to(message, reply.content)

"""
direct question to chatgpt 3
"""
@bot.message_handler(commands=['3'])
def echo_to_three(message):
    if authorized(message.chat.username, message.chat.id):
        messages.append(
            {
                "role": "user",
                "content": message.text
            },
        )

        chat = client.chat.completions.create(
            messages=messages,
            model=GPT3
        )

        reply = chat.choices[0].message
        bot.reply_to(message, reply.content)


# %%
"""
direct question to chatgpt (default)
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
            model=CURRENT_GPT_MODEL
        )

        reply = chat.choices[0].message
        bot.reply_to(message, reply.content)



# %%
bot.infinity_polling()

