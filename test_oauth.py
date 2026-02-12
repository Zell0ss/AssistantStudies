#!/usr/bin/env python3
"""
Script para verificar configuración OAuth Gmail existente
"""
import os
import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

def check_credentials_file():
    """Verifica el archivo credentials.json"""
    print("=" * 50)
    print("📋 VERIFICANDO ARCHIVO CREDENTIALS.JSON")
    print("=" * 50)
    
    if not os.path.exists(CREDENTIALS_FILE):
        print("❌ No se encontró credentials.json")
        print("   Debes descargarlo de Google Cloud Console")
        return False
    
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            creds_data = json.load(f)
        
        print("✅ Archivo credentials.json encontrado")
        
        if 'installed' in creds_data:
            client_info = creds_data['installed']
            print(f"   Client ID: {client_info['client_id'][:30]}...")
            print(f"   Project ID: {client_info.get('project_id', 'No especificado')}")
            print(f"   Auth URI: {client_info.get('auth_uri', 'No especificado')}")
            print("✅ Estructura del archivo parece correcta")
            return True
        else:
            print("❌ Estructura incorrecta - debe tener sección 'installed'")
            return False
            
    except json.JSONDecodeError:
        print("❌ El archivo credentials.json no es un JSON válido")
        return False
    except Exception as e:
        print(f"❌ Error leyendo credentials.json: {e}")
        return False

def check_existing_token():
    """Verifica si existe un token válido"""
    print("\n" + "=" * 50)
    print("🔑 VERIFICANDO TOKEN EXISTENTE")
    print("=" * 50)
    
    if not os.path.exists(TOKEN_FILE):
        print("❌ No existe token.json - necesitas autenticarte por primera vez")
        return None
    
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        print("✅ Token encontrado")
        print(f"   Válido: {'✅ Sí' if creds.valid else '❌ No'}")
        print(f"   Expirado: {'❌ Sí' if creds.expired else '✅ No'}")
        print(f"   Tiene refresh token: {'✅ Sí' if creds.refresh_token else '❌ No'}")
        
        if creds.expired and creds.refresh_token:
            print("🔄 Intentando renovar token...")
            try:
                creds.refresh(Request())
                print("✅ Token renovado exitosamente")
                
                # Guardar token renovado
                with open(TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
                print("✅ Token renovado guardado")
                return creds
            except Exception as e:
                print(f"❌ Error renovando token: {e}")
                return None
        
        return creds if creds.valid else None
        
    except Exception as e:
        print(f"❌ Error leyendo token: {e}")
        return None

def test_gmail_connection(creds):
    """Prueba la conexión con Gmail API"""
    print("\n" + "=" * 50)
    print("📧 PROBANDO CONEXIÓN GMAIL API")
    print("=" * 50)
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        
        # Prueba básica: obtener perfil
        profile = service.users().getProfile(userId='me').execute()
        print("✅ Conexión Gmail API exitosa")
        print(f"   Email: {profile.get('emailAddress')}")
        print(f"   Total mensajes: {profile.get('messagesTotal')}")
        
        # Prueba búsqueda básica
        results = service.users().messages().list(
            userId='me', 
            maxResults=1
        ).execute()
        
        messages = results.get('messages', [])
        print(f"   Puede acceder a mensajes: {'✅ Sí' if messages else '⚠️ Sin mensajes'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error conectando con Gmail API: {e}")
        return False

def do_initial_auth():
    """Realiza autenticación inicial si es necesario"""
    print("\n" + "=" * 50)
    print("🔐 AUTENTICACIÓN INICIAL")
    print("=" * 50)
    
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE, SCOPES)
        
        print("🌐 Abriendo navegador para autenticación...")
        print("   Si estás en servidor, usa SSH port forwarding:")
        print("   ssh -L 8080:localhost:8080 usuario@tu-servidor")
        
        creds = flow.run_local_server(
            port=8080, 
            access_type='offline',
            prompt='consent'  # Fuerza mostrar pantalla de consentimiento
        )
        
        # Guardar credenciales
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        
        print("✅ Autenticación completada y guardada")
        return creds
        
    except Exception as e:
        print(f"❌ Error en autenticación inicial: {e}")
        return None

def main():
    """Función principal de verificación"""
    print("🔍 VERIFICADOR DE CONFIGURACIÓN OAUTH GMAIL")
    print("=" * 60)
    
    # 1. Verificar credentials.json
    if not check_credentials_file():
        print("\n❌ CONCLUSIÓN: Necesitas descargar credentials.json de Google Cloud Console")
        return
    
    # 2. Verificar token existente
    creds = check_existing_token()
    
    # 3. Si no hay token válido, hacer autenticación inicial
    if not creds:
        print("\n🔄 Iniciando proceso de autenticación...")
        creds = do_initial_auth()
        
        if not creds:
            print("\n❌ CONCLUSIÓN: No se pudo completar la autenticación")
            return
    
    # 4. Probar conexión Gmail
    if test_gmail_connection(creds):
        print("\n" + "=" * 60)
        print("✅ TODO CONFIGURADO CORRECTAMENTE")
        print("   Tu configuración OAuth está lista para usar")
        print("   Puedes ejecutar tu aplicación FastAPI")
        print("=" * 60)
    else:
        print("\n❌ CONCLUSIÓN: Hay problemas con la conexión Gmail API")

if __name__ == "__main__":
    main()