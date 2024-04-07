#%%
import dropbox
import os
import yaml
from datetime import datetime

ruta_fichero = os.path.abspath(__file__)
directorio_actual = os.path.dirname(ruta_fichero)


# Local config.yaml
try:
    config_file = f"{directorio_actual}/../config.yaml"
    with open(config_file, 'r') as archivo_config:
        config = yaml.safe_load(archivo_config)
except FileNotFoundError:
    print("El archivo config.yaml no se encuentra en el directorio.")
    raise
except yaml.YAMLError as e:
    print(f"Error al cargar el archivo config.yaml: {e}")
    raise

#%%
# connection to dropbox
# dbx = dropbox.Dropbox(oauth2_access_token=config["dropbox"]["access_token"])
dbx = dropbox.Dropbox(oauth2_refresh_token=config["dropbox"]["refresh_token"],
                        app_key=config["dropbox"]["app_key"],
                        app_secret=config["dropbox"]["app_secret"])
try:
    dbx.users_get_current_account()
except Exception as exc:
    print(exc)
#%%
# test functions
    
def test_list_folders():
#files in Espacio Familiar
    for entry in dbx.files_list_folder('id:I9qyFus3r3cAAAAAAAxXUg').entries:
        print(entry.name, entry.id)

def upload_tests():
# test upload a file
    test_file = f"{directorio_actual}/test.txt"
    target = "/Espacio familiar/intercambio/"
    targetfile = target + "test.txt"
    with open(test_file, 'rb') as f:
        metadata = dbx.files_upload(f.read(), targetfile, mode=dropbox.files.WriteMode("overwrite"))

# %%
def upload_file_dbx(file_blob, file_name:str, folder:str):
    target = f"/Espacio familiar/{folder}/{file_name}"
    metadata = dbx.files_upload(file_blob, target, mode=dropbox.files.WriteMode("overwrite"))
    return metadata

    
# %%
