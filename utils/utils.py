import yaml
import os
import re
import logging
import requests
import subprocess
"""
collection of utility functions for the Telegram bot
"""

"""
load config file
"""
config = {}
config_file = ""

try:
    ruta_fichero = os.path.abspath(__file__)
    config_file = ruta_fichero.replace("utils.py", "../config.yaml")
    with open(config_file, 'r') as archivo_config:
        config = yaml.safe_load(archivo_config)
except FileNotFoundError:
    print("El archivo config.yaml no se encuentra en el directorio.")
    raise
except yaml.YAMLError as e:
    the_error = f"Error al cargar el archivo config.yaml: {e}"
    print(the_error)
    raise

logging.basicConfig(filename=f'{config["logfolder"]}/app.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')
logging.warning('Loading config')
logging.warning("config loaded")

BOT_TOKEN = config["telegram_apikey"]

def authorized(username, userid):
    """
    Checks if a user is authorized to use the bot.
    
    Parameters
    username : str The username of the user.
    userid : str The user id of the user.
    
    Returns
    bool True if the user is authorized, False otherwise.
    """
    if  username in config["authorized_users"] or userid in config["authorized_ids"]:
        return True
    return False

def add_authorized_user(userid):
    #add uid to current auth users
    """
    Agrega un usuario a la lista de usuarios autorizados en el archivo de configuracion.
    
    Parameters
    userid : str  El UID del usuario que se va a agregar a la lista de usuarios autorizados.
    
    Returns
    config : dict La configuracion actualizada con el nuevo usuario autorizado.
    """
    config["authorized_users"].append(userid) 
    
    #add uid to file so it will be there if we restart
    with open(config_file, 'w') as archivo_config:
        yaml.dump(config, archivo_config, default_flow_style=False)
    return config

def restart_service():
    """
    Restarts the sebastian service using systemctl. This is useful if you want to reload the configuration.
    """
    command = "sudo systemctl restart sebastian.service"

    # Execute the command using subprocess
    process = subprocess.Popen(command, shell=True)
    process.wait()


def stop_service():
    """
    Stops the sebastian service using systemctl. You will need to manually restart it.
    """
    command = "sudo systemctl stop sebastian.service"

    # Execute the command using subprocess
    process = subprocess.Popen(command, shell=True)
    process.wait()


def retrieve_telegram_file_address(file_id):
    """
    Sends a request to the Telegram Bot API to get the file path associated with the given file ID. 

    Parameters
    file_id : str  The ID of the file in Telegram.

    Returns
    str or None  The file path if the request is successful, or None if it fails.
    """

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    response = requests.get(url)
    res_json = response.json()
    if res_json["ok"]:
        return res_json["result"]["file_path"]
    else: 
        return None
    
def retrieve_telegram_file(remote_name):
    """
    Retrieves the content of a Telegram file using its remote address.

    Parameters
    remote_name : str The remote address of the file in Telegram, as returned by the retrieve_telegram_file_address.

    Returns
    bytes or None The content of the file if the request is successful, or None if it fails.
    """
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{remote_name}"
    response_file = requests.get(url)
    das_file = response_file.content
    return das_file
    
def upload_document_dropbox(message, storage_provider):
    """
    Sube un documento a dropbox en el directorio especificado por el usuario.

    Parameters
    message : telebot.types.Message El mensaje que contiene el documento que se va a subir.
    storage_provider : StorageProvider The storage provider instance to use for upload.

    Returns
    str Un mensaje que indica el resultado de la subida del documento.
    """
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
    storage_provider.upload_file(file_blob=das_file, file_name=name, folder=folder)
    response =  f'Documento subido a {remote_name} depositado en dropbox Espacio familiar/{folder}/{name}'
    return response


def classify_text_mimetype(mime_type):
    """
    Classify the MIME type of a file and return a corresponding file type label.

    Parameters
    mime_type : str The MIME type of the file to classify.

    Returns 
    str
        A label representing the type of file. Possible return values are:
        - "pdf" for PDF documents
        - "doc" for Word documents
        - "txt" for plain text files
        - "jpg" for JPEG images
        - "png" for PNG images
        - "unk" for unknown or unsupported file types
    """

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
    """
    Escapes special characters for a given text so that it can be formatted as markdown.

    Parameters 
    text : str The text to be escaped.

    Returns 
    str The escaped text.

    Notes
    Characters that are escaped are: \\ _ * [ ] ( ) ~ > # + = | { } . !
    """
    # parser_chars=["\\", "_", "*", "[", "]", "(", ")", "~", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    # characters_to_escape = r'_\*\[\]\(\)~`>#+-=|{}.!'
    escaped_text = re.sub(r'([_\*\[\]\(\)~`>#+-=|{}.!])', r'\\\1', text)
    return escaped_text

def parse_nota_cata(nota_cata:str):
    """
    Parse a string containing a wine tasting note into a dictionary.

    Parameters
    nota_cata : str The string containing the wine tasting note. The string should be formatted with one key-value pair per line, separated by a colon.

    Returns
    dict A dictionary containing the key-value pairs from the string.

    Examples
    >>> parse_nota_cata("Bodega: Bodegas Lecea\nAñada: \nRegión: Rioja, Haro\nUvas:\nNota de cata visual: rojo picota casi violáceo con ribete morado. lágrima abundante que justifican sus 14.5 grados")
    {'Bodega': 'Bodegas Lecea', 'Añada': '', 'Región': 'Rioja, Haro', 'Uvas': '', 'Nota de cata visual': 'rojo picota casi violáceo con ribete morado. lágrima abundante que justifican sus 14.5 grados'}
    """
    lines = nota_cata.strip().split('\n')
    nota_cata_dic = {}
    for line in lines:
        key, value = line.split(':')
        nota_cata_dic[key.strip()] = value.strip()

    return nota_cata_dic