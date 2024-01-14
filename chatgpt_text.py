#%%
from openai import OpenAI
import pyttsx3
import os

#%%
import yaml

# Intenta cargar el archivo config.yaml desde el mismo directorio
try:
    ruta_fichero = os.path.abspath(__file__)
    config_file = ruta_fichero.replace("chatgpt_text.py", "config.yaml")
    with open(config_file, 'r') as archivo_config:
        config = yaml.safe_load(archivo_config)
except FileNotFoundError:
    print("El archivo config.yaml no se encuentra en el directorio.")
except yaml.YAMLError as e:
    print(f"Error al cargar el archivo config.yaml: {e}")

#%%
engine_sp = pyttsx3.init()
engine_sp.setProperty('voice', "spanish")
def leeme_esto(message):
    engine_sp.say(message)
    engine_sp.runAndWait()

#%%
client = OpenAI(api_key = config['openai_apikey'])

messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant"
    }
]

while True:
    message = input("λ> ")

    messages.append(
        {
            "role": "user",
            "content": message
        },
    )

    chat = client.chat.completions.create(
        messages=messages,
        model="gpt-3.5-turbo"
    )

    reply = chat.choices[0].message

    print("Sebastian: ", reply.content)
    # leeme_esto(reply.content)
    
    messages.append(reply)
# %%
