# modules/salud.py
"""
Salud module — cliente de la tool `salud` hacia la API de ingesta de Tristras (D39-D42).

Sin DB ni estado por usuario: un solo proxy HTTP. El texto del mensaje y lo que lee el
modelo nunca se guardan en Sebastian — D3/D39 dicen que el conocimiento de salud y sus
datos viven en Tristras, Sebastian es solo el canal.
"""
import requests
from logcentral_client import get_logger

logger = get_logger("sebastian")

_TIMEOUT_S = 30
_MENSAJE_SIN_RESPUESTA = "No he podido apuntar tu sueño ahora mismo; pruébalo en un rato."


class SaludModule:

    def __init__(self, base_url: str, token: str):
        self._base_url = base_url.rstrip("/")
        self._token = token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def _parse(self, response) -> dict:
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code >= 400:
            # H2-revision.md (anexo a H2): el detail de un 422/503 es una frase ya pensada
            # para el usuario ("Las fases leídas no cuadran con el total dormido.",
            # "No he podido leerlo ahora; prueba en un rato.") — se reenvía tal cual.
            detail = data.get("detail") if isinstance(data, dict) else None
            return {"tipo": "error", "resumen": detail or _MENSAJE_SIN_RESPUESTA}
        return data

    def registrar_texto(self, mensaje: str) -> str:
        """Manda `mensaje` a /api/ingesta/texto. Devuelve siempre una frase para el usuario
        (resumen, tipo "sueno" o "no_entendido"; el detail de un error si lo hubo)."""
        try:
            response = requests.post(
                f"{self._base_url}/api/ingesta/texto",
                headers=self._headers(),
                json={"texto": mensaje},
                timeout=_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            logger.warning(f"Tristras no respondió a /api/ingesta/texto: {type(exc).__name__}")
            return _MENSAJE_SIN_RESPUESTA
        return self._parse(response).get("resumen", "Apuntado.")

    def registrar_captura(self, imagen_bytes: bytes, filename: str, content_type: str) -> dict:
        """Manda una imagen a /api/ingesta/captura. Devuelve el JSON tal cual lo da Tristras
        ({"tipo": "sueno", "registro": ..., "resumen": ...} | {"tipo": "desconocida"} |
        {"tipo": "error", "resumen": ...} en fallos de red o de la API) — quien llama decide
        qué decir según `tipo` (D40: "desconocida" usa la respuesta de siempre, no un texto
        de Tristras)."""
        try:
            response = requests.post(
                f"{self._base_url}/api/ingesta/captura",
                headers=self._headers(),
                files={"imagen": (filename, imagen_bytes, content_type)},
                timeout=_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            logger.warning(f"Tristras no respondió a /api/ingesta/captura: {type(exc).__name__}")
            return {"tipo": "error", "resumen": _MENSAJE_SIN_RESPUESTA}
        return self._parse(response)
