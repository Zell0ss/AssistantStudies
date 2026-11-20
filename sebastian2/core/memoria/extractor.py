"""Extractor de hechos (fase 2, D32): Haiku 4.5 con una tool forzada, `registrar_hechos`.

Recibe el catalogo del usuario y la fecha de hoy y devuelve una lista de hechos estructurados. El LLM
propone nombres; quien decide es el codigo (D8, `resolucion.py`). Haiku 4.5 y no 5.5: mismo modelo que
el planner (D29); la tool forzada da un JSON valido en 4.5.
"""
from datetime import date
from pathlib import Path

from logcentral_client import get_logger

logger = get_logger("sebastian")

# D32: modelo del extractor, en un solo sitio.
MODELO_EXTRACTOR = "claude-haiku-4-5-20251001"
MAX_HECHOS = 8
_TOKENS_MAXIMOS = 2048
TIPOS_ENTIDAD = ("persona", "proyecto", "vehiculo", "lugar", "mascota", "organizacion", "objeto", "otro")
_OPERACIONES = ("afirmar", "corregir", "retirar")
_TIPOS_VALOR = ("texto", "numero", "fecha", "booleano")
_PROMPT = Path(__file__).parent / "prompts" / "extractor_hechos.md"

TOOL_REGISTRAR_HECHOS = {
    "name": "registrar_hechos",
    "description": "Registra los hechos que afirma la frase del usuario. Lista vacía si no hay ninguno duradero.",
    "input_schema": {
        "type": "object",
        "properties": {
            "hechos": {
                "type": "array",
                "maxItems": MAX_HECHOS,
                "items": {
                    "type": "object",
                    "properties": {
                        "entidad": {"type": "string", "description": "De quién o de qué habla; `yo` si es el propio usuario."},
                        "tipo_entidad": {"type": "string", "enum": list(TIPOS_ENTIDAD)},
                        "atributo": {"type": "string", "description": "snake_case sin tildes; el del catálogo si existe."},
                        "tipo_valor": {"type": "string", "enum": list(_TIPOS_VALOR)},
                        "cardinalidad": {"type": "string", "enum": ["uno", "varios"]},
                        "valor": {"type": "string", "description": "Tal cual lo dijo el usuario; fechas en ISO."},
                        "operacion": {"type": "string", "enum": list(_OPERACIONES)},
                        "descripcion_atributo": {"type": "string", "description": "Solo para un atributo nuevo: una frase general."},
                    },
                    "required": ["entidad", "atributo", "operacion"],
                },
            }
        },
        "required": ["hechos"],
    },
}


def _prompt(catalogo: str, hoy: date) -> str:
    # replace y no format: el prompt lleva llaves de ejemplo y el catalogo, texto libre del usuario.
    return _PROMPT.read_text().replace("{hoy}", hoy.isoformat()).replace("{catalogo}", catalogo)


def es_marcador(entidad: str) -> bool:
    """`<UNKNOWN>`, `<desconocido>`…: el modelo no sabe de quién habla y deja un marcador en vez de una entidad
    (H3-revision R10). Un nombre que solo empieza o solo termina en «<» o «>» («<3») es un nombre."""
    e = entidad.strip()
    return not e or (e.startswith("<") and e.endswith(">"))


def _motivo_de_descarte(crudo) -> str | None:
    """Por qué `_validar` tira este crudo, como etiqueta fija (D42: nunca el valor), o None si lo deja pasar.
    Mismo orden que `_validar`; tiene que decir lo mismo que él (lo comprueba una prueba)."""
    if not isinstance(crudo, dict):
        return "no_es_dict"
    if es_marcador(str(crudo.get("entidad") or "").strip()):
        return "marcador"
    if not str(crudo.get("atributo") or "").strip():
        return "sin_atributo"
    if crudo.get("operacion") not in _OPERACIONES:
        return "operacion_invalida"
    return None


def _validar(crudo) -> dict | None:
    """Un hecho bien formado con valores por defecto, o None si no sirve (también si su entidad es un marcador)."""
    if not isinstance(crudo, dict):
        return None
    entidad = str(crudo.get("entidad") or "").strip()
    atributo = str(crudo.get("atributo") or "").strip()
    operacion = crudo.get("operacion")
    if es_marcador(entidad) or not atributo or operacion not in _OPERACIONES:
        return None
    tipo_entidad = crudo.get("tipo_entidad")
    tipo_valor = crudo.get("tipo_valor")
    return {
        "entidad": entidad,
        "tipo_entidad": tipo_entidad if tipo_entidad in TIPOS_ENTIDAD else "otro",
        "atributo": atributo,
        "tipo_valor": tipo_valor if tipo_valor in _TIPOS_VALOR else "texto",
        "cardinalidad": "varios" if crudo.get("cardinalidad") == "varios" else "uno",
        "valor": str(crudo.get("valor") or "").strip(),
        "operacion": operacion,
        "descripcion_atributo": str(crudo.get("descripcion_atributo") or "").strip(),
    }


class Extractor:
    def __init__(self, cliente, modelo: str = MODELO_EXTRACTOR, on_usage=None):
        self._cliente = cliente
        self._modelo = modelo
        self._on_usage = on_usage
        self.marcadores_descartados = 0   # de la última llamada: el servicio avisa de que no supo de quién se hablaba

    def extraer(self, texto: str, catalogo: str, hoy: date) -> list[dict]:
        """Hechos de `texto`. Un fallo de la API se propaga: quien llama decide como degradar."""
        self.marcadores_descartados = 0
        self.ultimo_input = None      # D72: `bloque.input` crudo de la última llamada, para la traza de depuración (no se loguea)
        respuesta = self._cliente.messages.create(
            model=self._modelo,
            max_tokens=_TOKENS_MAXIMOS,
            system=_prompt(catalogo, hoy),
            tools=[TOOL_REGISTRAR_HECHOS],
            tool_choice={"type": "tool", "name": TOOL_REGISTRAR_HECHOS["name"]},
            messages=[{"role": "user", "content": texto}],
        )
        if self._on_usage is not None:
            self._on_usage(respuesta, self._modelo)
        bloque = next((b for b in respuesta.content
                       if getattr(b, "type", None) == "tool_use" and b.name == TOOL_REGISTRAR_HECHOS["name"]), None)
        if bloque is None:
            logger.warning("Extractor: la respuesta no trae la tool registrar_hechos")
            return []
        self.ultimo_input = bloque.input
        crudos = (bloque.input or {}).get("hechos") or []
        descartes = []
        if not isinstance(crudos, list):
            # Antes, `or []` solo tapaba lo vacío; un texto o un número «de hechos» se iteraba carácter a carácter o rompía.
            crudos, descartes = [], ["hechos_no_lista"]
        self.marcadores_descartados = sum(1 for c in crudos if isinstance(c, dict)
                                          and es_marcador(str(c.get("entidad") or "")) and c.get("entidad"))
        validados = [h for h in map(_validar, crudos) if h][:MAX_HECHOS]
        descartes += [m for m in map(_motivo_de_descarte, crudos) if m]
        # H1c (R10b, D42): qué devolvió el modelo, para distinguir «Haiku no devolvió nada» de «`_validar` lo tiró todo».
        # Solo el motivo, como etiqueta fija: nunca un valor ni texto del modelo.
        logger.info(f"Extractor: stop={getattr(respuesta, 'stop_reason', None)} crudos={len(crudos)} validados={len(validados)}"
                    + (f" descartes={','.join(descartes)}" if descartes else ""))
        return validados
