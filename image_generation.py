from openai import OpenAI
import os
from colorama import Fore

#%%
import yaml

# Intenta cargar el archivo config.yaml desde el mismo directorio
try:
    ruta_fichero = os.path.abspath(__file__)
    config_file = ruta_fichero.replace("image_generation.py", "config.yaml")
    with open(config_file, 'r') as archivo_config:
        config = yaml.safe_load(archivo_config)
except FileNotFoundError:
    print("El archivo config.yaml no se encuentra en el directorio.")
    raise
except yaml.YAMLError as e:
    print(f"Error al cargar el archivo config.yaml: {e}")
    raise

client = OpenAI(api_key = config['openai_apikey'])

messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant"
    }
]
#%%
os.system("clear")
while True:
    print(Fore.RED +"*"+Fore.LIGHTBLUE_EX+" ----------------------------------------"+Fore.MAGENTA+"o"+Fore.BLUE+"="+Fore.WHITE+"x ")
    message = input("λ> ")
    # message = "I NEED to test how the tool works with extremely simple prompts. DO NOT add any detail, just use it AS-IS: "+ message

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=message,
            size="1024x1024",
            quality="standard",
            n=1,
            )
        image_url = response.data[0].url
        revised_prompt = response.data[0].revised_prompt
    except Exception as exc:
        image_url = "failure"
        revised_prompt = exc



    print("")
    print(Fore.YELLOW+"Sebastian: "+Fore.GREEN, revised_prompt )
    print(image_url)