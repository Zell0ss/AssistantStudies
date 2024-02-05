# connect to https://console.cloud.google.com and create a new project
# enable api library https://console.cloud.google.com/apis/library?organizationId=0&project=api-access-412820
# create Oauth and service account + API Key in https://console.cloud.google.com/apis/credentials?project=api-access-412820 
# store the both json created
# share the calendar to the service account

# %%
from datetime import datetime, timedelta
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import yaml

scopes=['https://www.googleapis.com/auth/calendar']

ruta_fichero = os.path.abspath(__file__)
directorio_actual = os.path.dirname(ruta_fichero)

# %%
service_api_file = f'{directorio_actual}/Zell0ss_api-access.json'
try:
    service_cred = service_account.Credentials.from_service_account_file(service_api_file, scopes=scopes)
    service = build('calendar', 'v3', credentials=service_cred)
    # suscribir a mis eventos
    service.calendarList().insert(body={'id': 'zelloss@gmail.com'})
    service.calendarList().list().execute()
except Exception as e:
    print(f"Error al procesar el archivo de service account api access: {e}")
    raise

#%%
# oauth_file = f'{directorio_actual}/Zell0ss_credentials.json'
# creds = None
# if os.path.exists('token.json'):
#     creds = Credentials.from_authorized_user_file('token.json', scopes)
# if not creds or not creds.valid:
#     if creds and creds.expired and creds.refresh_token:
#         creds.refresh(Request())
#     else:
#         flow = InstalledAppFlow.from_client_secrets_file(oauth_file, scopes)
#         creds = flow.run_local_server(port=0)
#     # Save the credentials for the next run
#     with open('token.json', 'w') as token:
#         token.write(creds.to_json())
# service = build('calendar', 'v3', credentials=creds)

# %%
# Crear instancia del cliente de Google Calendar API


def get_events():

    manana = datetime.now() + timedelta(days=1)
    fecha_hoy = datetime.now().date().isoformat()
    fecha_manana = manana.date().isoformat()

    # Obtener eventos para hoy y mañana

    eventos = service.events().list(calendarId='zelloss@gmail.com', timeMin=fecha_hoy + 'T00:00:00Z',
                                timeMax=fecha_manana + 'T23:59:59Z').execute()

    # Imprimir los eventos
    eventos_str = ""
    if eventos['items']:
        for evento in eventos['items']:
            eventos_str = f'Título: {evento["summary"]} \n'
            if evento['start'].get('date'):
                eventos_str += f'Fecha: {evento["start"].get("date")} \n'
            else:
                eventos_str += f'Fecha: {evento["start"].get("dateTime")[0:16]} \n' 
    else:
        return ('No hay eventos programados entre hoy y mañana.')
    return eventos_str


# %%
print (get_events())

# %%

