#%%
import os
from openai import OpenAI
import time
import speech_recognition as sr
import pyttsx3
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
# import gtts
# gtts.lang.tts_langs()


#%%
mytext = 'Bienvenido al asistente'
language = 'es'
name = "Josem"
wake_word = "sebasti"
greetings = [f"¿Que desea, amo {name}?",
             "¿Si, señor?",
             f"Capitán en el puente!"]

# set up openai 
chatgpt_client = OpenAI(api_key = config['openai_apikey'])



# Set up the speech recognition 
r = sr.Recognizer()

#%%
# Listen for the wake word "hey pos"
def listen_for_wake_word(source, wake_word:str):
    print(f"Listening for '{wake_word}'...")

    while True:
        audio = r.listen(source)
        try:
            print(">>debug:Speech detected")
            text = r.recognize_google(audio, language="es-ES")
            if wake_word in text.lower():
                print(">>debug:Wake word detected.")
                leeme_esto(np.random.choice(greetings))
                listen_and_respond(source)
                break
            print(f">>debug: {text}.")
        except sr.UnknownValueError:
            pass

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
def conversion_to_audio(response_text:str, lang:str="en"):
    myobj = gTTS(text = response_text, lang=lang, slow = False)
    myobj.save("test.wav")
    os.system("aplay test.wav")

#%%
# set up tts engine
# engine_en = pyttsx3.init()
# engine_en.setProperty('voice', "english")
# def read_this(message):
#     engine_en.say(message)
#     engine_en.runAndWait()    

engine_sp = pyttsx3.init()
engine_sp.setProperty('voice', "spanish")
def leeme_esto(message):
    engine_sp.say(message)
    engine_sp.runAndWait()



#%%
# Listen for input and respond with OpenAI API
def listen_and_respond(source):
    print("Listening...")

    while True:
        audio = r.listen(source)
        try:
            text = r.recognize_google(audio, language="es-ES")
            print(f">>debug:You said: {text}")
            if not text:
                continue

            # Send input to OpenAI API
            response_text=send_to_openai(text) 

            # tts with google
            # conversion_to_audio(response_text, "sp")

            # tts with pyttsx3
            print(">>debug:speaking")
            leeme_esto(response_text)

            if not audio:
                listen_for_wake_word(source, wake_word)
        except sr.UnknownValueError:
            time.sleep(2)
            print(">>debug:Silence found, shutting up, listening...")
            listen_for_wake_word(source, wake_word)
            break

        except sr.RequestError as e:
            print(f"Could not request results; {e}")
            leeme_esto("No se han podido conseguir los resultados")
            read_this(f"error: {e}")
            listen_for_wake_word(source, wake_word)
            break

# Use the default microphone as the audio source
with sr.Microphone() as source:
    listen_for_wake_word(source, wake_word)