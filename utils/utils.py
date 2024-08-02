import yaml
import os
import logging
import requests
from mydropbox.upload_dropbox import upload_file_dbx
logging.basicConfig(filename="/home/konnos/data/tests/logs/app.log", filemode='w', format='%(name)s - %(levelname)s - %(message)s')
logging.warning('Loading config')


config = {}
config_file = ""
# Intenta cargar el archivo config.yaml desde el mismo directorio
try:
    ruta_fichero = os.path.abspath(__file__)
    config_file = ruta_fichero.replace("utils.py", "../config.yaml")
    with open(config_file, 'r') as archivo_config:
        config = yaml.safe_load(archivo_config)
except FileNotFoundError:
    print("El archivo config.yaml no se encuentra en el directorio.")
    logging.error("El archivo config.yaml no se encuentra en el directorio.")
    raise
except yaml.YAMLError as e:
    the_error = f"Error al cargar el archivo config.yaml: {e}"
    print(the_error)
    logging.error(the_error)
    raise
logging.warning("config loaded")

BOT_TOKEN = config["telegram_apikey"]

def authorized(username, userid):
    if  username in config["authorized_users"] or userid in config["authorized_ids"]:
        return True
    return False

def add_authorized_user(userid):
    #add uid to current auth users
    config["authorized_users"].append(userid) 
    
    #add uid to file so it will be there if we restart
    with open(config_file, 'w') as archivo_config:
        yaml.dump(config, archivo_config, default_flow_style=False)

    return config

def retrieve_telegram_file_address(file_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    response = requests.get(url)
    res_json = response.json()
    if res_json["ok"]:
        return res_json["result"]["file_path"]
    else: 
        return None
    
def retrieve_telegram_file(remote_name):
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{remote_name}"
    response_file = requests.get(url)
    das_file = response_file.content
    return das_file
    
def upload_document_dropbox(message):
    if hasattr(message, "caption") and message.caption:
        folder=message.caption
    elif hasattr(message, "html_caption") and message.html_caption:
        folder=message.html_caption
    else:
        folder = "intercambio"
    name=message.document.file_name
    # retrieve address of the file in telegram site
    remote_name = retrieve_telegram_file_address(message.document.file_id)
    #retrieve file itself
    das_file = retrieve_telegram_file(remote_name)
    #to dropbox!
    upload_file_dbx(file_blob=das_file, file_name=name, folder=folder)
    response =  f'Documento subido a {remote_name} depositado en dropbox Espacio familiar/{folder}/{name}'
    return response


def classify_text_mimetype(mime_type):
    if mime_type == 'application/pdf':
        return "pdf"
    elif mime_type == 'application/msword' or mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        return "doc"
    elif mime_type == 'text/plain':
        return "txt"
    elif mime_type == 'image/jpeg':
        return "jpg"
    elif mime_type == 'image/png':
        return "png"
    elif mime_type == "text/plain":
        return "txt"
    else:
        return "unk"
    
def parse_for_markdown(text:str):
    return None