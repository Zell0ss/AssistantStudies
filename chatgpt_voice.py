#%%
import os
import openai
from dotenv import load_dotenv
import time
import speech_recognition as sr
import pyttsx3
import numpy as np
from gtts import gTTS
import subprocess
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
gtts.lang.tts_langs()


#%%
mytext = 'Welcome to me'
language = 'en'

openai.api_key=config['openai_apikey']
load_dotenv()
model = 'gpt-3.5-turbo'
# Set up the speech recognition and text-to-speech engines
r = sr.Recognizer()
engine = pyttsx3.init("dummy")
voice = engine.getProperty('voices')[1]
engine.setProperty('voice', voice.id)
name = "Josem"
greetings = [f"whats up master {name}",
             "yeah?",
             "Yes, master Josem?",
             f"Captain on the bridge!"]

# Listen for the wake word "hey pos"
def listen_for_wake_word(source):
    print("Listening for 'Alfred'...")

    while True:
        audio = r.listen(source)
        try:
            text = r.recognize_google(audio)
            if "Alfred" in text.lower():
                print("Wake word detected.")
                engine.say(np.random.choice(greetings))
                engine.runAndWait()
                listen_and_respond(source)
                break
        except sr.UnknownValueError:
            pass

def send_to_openai(text):
    # Send input to OpenAI API
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", 
                                            messages=[{"role": "user", 
                                                       "content": f"{text}"}])
    response_text = response.choices[0].message.content
    print(response_text)
    return (response_text)

def conversion_to_audio(response_text:str, lang:str="en"):
    myobj = gTTS(text = response_text, lang=lang, slow = False)
    myobj.save("test.wav")
    os.system("aplay test.wav")

# Listen for input and respond with OpenAI API
def listen_and_respond(source):
    print("Listening...")

    while True:
        audio = r.listen(source)
        try:
            text = r.recognize_google(audio)
            print(f"You said: {text}")
            if not text:
                continue

            # Send input to OpenAI API
            response_text=send_to_openai(text) 

            # test conversion to audio with google
            # conversion_to_audio(response_text)

            # Speak the response
            print("speaking")
            os.system("espeak ' "+response_text + "'")
            engine.say(response_text)
            engine.runAndWait()

            if not audio:
                listen_for_wake_word(source)
        except sr.UnknownValueError:
            time.sleep(2)
            print("Silence found, shutting up, listening...")
            listen_for_wake_word(source)
            break

        except sr.RequestError as e:
            print(f"Could not request results; {e}")
            engine.say(f"Could not request results; {e}")
            engine.runAndWait()
            listen_for_wake_word(source)
            break

# Use the default microphone as the audio source
with sr.Microphone() as source:
    listen_for_wake_word(source)