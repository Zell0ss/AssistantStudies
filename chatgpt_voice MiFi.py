#%%
import os
from openai import OpenAI
import time
import speech_recognition as sr
import numpy as np
from gtts import gTTS


#%%
import yaml

# Intenta cargar el archivo config.yaml desde el mismo directorio
try:
    with open("config.yaml", 'r') as archivo_config:
        config = yaml.safe_load(archivo_config)
except FileNotFoundError:
    print("El archivo config.yaml no se encuentra en el directorio.")
except yaml.YAMLError as e:
    print(f"Error al cargar el archivo config.yaml: {e}")
   
#%%
WAKE_WORD = "aurora"
greetings = [f"¿Que desea, señor?",
             "¿Si, señor?",
             f"Capitán en el puente!"]
ALTAVOZ = True
MP3_BATCH_FILE = "output.mp3"

# set up openai 
chatgpt_client = OpenAI(api_key = config['openai_apikey'])

# Set up the speech recognition 
r = sr.Recognizer()



#%%
def send_to_openai(text):
    # Send input to OpenAI API
    messages = [
    {"role": "system","content": "You are a helpful assistant"},
    {"role": "user", "content": f"{text}"}
]
    response = chatgpt_client.chat.completions.create(model="gpt-3.5-turbo", 
                                            messages=messages)
    response_text = response.choices[0].message.content
    print(response_text)
    return (response_text)

#%%
def lee_via_mp3(response_text:str, lang:str="es"):
    myobj = gTTS(text = response_text, lang=lang, slow = False)
    myobj.speed = 4 
    myobj.save(MP3_BATCH_FILE)
    os.system(f"play -q {MP3_BATCH_FILE} tempo 1.5")
    print(f">>debug: Finished enunciation")


#%%
# Listen for the wake word "hey pos"
def listen_for_wake_word(source):
    print(f">>sleep:Listening for '{WAKE_WORD}'.")

    while True:
        audio = r.listen(source)
        try:
            print(">>sleep:Speech detected")
            text = r.recognize_google(audio, language="es-ES")
            if WAKE_WORD in text.lower():
                print(">>sleep:Wake word detected.")
                lee_via_mp3(np.random.choice(greetings))
                listen_and_respond(source)
                break
            print(f">>sleep: {text}.")
        except sr.UnknownValueError:
            print(">>sleep:Noise, ignored")
            pass

#%%
# Listen for input and respond with OpenAI API
def listen_and_respond(source):
    global ALTAVOZ
    print(">>active: Waiting query.")

    while True:
        audio = r.listen(source)
        try:
            text = r.recognize_google(audio, language="es-ES")
            print(f">>active: Received: {text}")
            if not text:
                continue
            elif text == "ayuda":
                response_text="Estas son unas sencillas instrucciones. \
                            Para despertarme y que te atienda simplemente di mi nombre y espera a que te conteste. \
                            En general, siempre que me digas algo deber esperar mi contestacion antes de preguntar otra cosa. \
                            Una vez despierto, para que te responda a una pregunta enunciala sin mas y espera mi respuesta. \
                            Si quieres respuestas solo en texto di apaga altavoz. Si quieres que lo encienda de nuevo di enciende altavoz. \
                            Si quieres que vuelva a mi estado de reposo di descansa y no respondere nada mas hasta que me actives primero llamandome por mi nombre"
            elif text == "apaga altavoz":
                response_text="altavoz apagado"
                ALTAVOZ = False
            elif text == "enciende altavoz":
                response_text="altavoz encendido"
                ALTAVOZ = True
            elif text == "descansa":
                print(">>active: Force to return to sleep")
                listen_for_wake_word(source)
                break
            else:
                # Send input to OpenAI API
                response_text=send_to_openai(text) 
            if ALTAVOZ:
                print(">>active: speaking")
                lee_via_mp3(response_text)

            if not audio:
                listen_for_wake_word(source)
        except sr.UnknownValueError:
            time.sleep(2)
            print(">>active: Silence found, shutting up, listening...")
            listen_for_wake_word(source)
            break
        except sr.RequestError as e:
            print(f">>active: Could not request results; {e}")
            lee_via_mp3("No se han podido conseguir los resultados")
            lee_via_mp3(f"error: {e}", lang = "en")
            listen_for_wake_word(source)
            break
        except Exception as exc:
            print(f">>active: exception {exc}")
            break
#%%
# Use the default microphone as the audio source
with sr.Microphone() as source:
    listen_for_wake_word(source)
# %%
