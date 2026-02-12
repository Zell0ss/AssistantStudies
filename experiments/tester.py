#%%
from sebastian_agent import get_sebastian_answer
get_sebastian_answer("promueve mi articulo https://gotasdivinas.blogspot.com/2025/07/nota-de-cata-vigna-roca-albana-secco.html en las redes sociales")


#%%
from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

try:
    with open('credentials.json', 'r') as f:
        creds_data = json.load(f)
        print("✅ Archivo credentials.json encontrado")
        print(f"Client ID: {creds_data['installed']['client_id'][:20]}...")
        print("✅ Configuración OAuth parece válida")
except FileNotFoundError:
    print("❌ No se encontró credentials.json - necesitas crearlo")
except Exception as e:
    print(f"❌ Error en credentials.json: {e}")
# %%
