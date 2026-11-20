# modules/vigilancias/fuentes/__init__.py
"""Las fuentes de vigilancias (plan §2.2). Una fuente es un objeto con `nombre` y `buscar(consulta) -> list[Anuncio]`, que
lanza `FuenteError` si la consulta falla. Se registra aquí; añadir una no cambia la BD (`vigilancias.fuente` es texto)."""
from modules.vigilancias.anuncio import Anuncio, FuenteError
from modules.vigilancias.fuentes.wallapop import Wallapop

FUENTES = {"wallapop": Wallapop()}

__all__ = ["Anuncio", "FUENTES", "FuenteError", "Wallapop"]
