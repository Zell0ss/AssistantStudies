"""Piezas falsas para las pruebas de vigilancias (fase 4): anuncios, fuentes, cliente de Anthropic y bot. Todos los datos de
los anuncios son INVENTADOS."""
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from modules.vigilancias.anuncio import Anuncio, FuenteError

AHORA = datetime(2026, 11, 20, 7, 30)          # un viernes


def hacer_anuncio(id="a1", titulo="Mac mini M4 24 GB", descripcion="Como nuevo, con caja.", precio="900", ciudad="Valencia",
                  modificado=None, reservado=False, envio=True, fuente="wallapop", **extra) -> Anuncio:
    return Anuncio(
        fuente=fuente, id=id, titulo=titulo, descripcion=descripcion,
        precio=None if precio is None else Decimal(str(precio)), moneda="EUR", ciudad=ciudad,
        url=f"https://es.wallapop.com/item/{id}-slug", modificado=modificado or datetime(2026, 11, 20, 6, 0),
        reservado=reservado, envio=envio, vendedor="vendedor-1", **extra)


class FuenteFalsa:
    """`respuestas`: {consulta: [Anuncio] | Exception}. Una consulta sin entrada devuelve []."""
    nombre = "wallapop"

    def __init__(self, respuestas=None, por_defecto=None):
        self.respuestas, self.por_defecto, self.consultas = respuestas or {}, por_defecto, []

    def buscar(self, consulta):
        self.consultas.append(consulta)
        r = self.respuestas.get(consulta, self.por_defecto if self.por_defecto is not None else [])
        if isinstance(r, Exception):
            raise r
        return list(r)


def fuente_que_falla(*, fallan: int):
    """Una fuente donde las `fallan` primeras consultas distintas lanzan FuenteError (con la consulta en el mensaje, a propósito)."""
    class _F(FuenteFalsa):
        def buscar(self, consulta):
            self.consultas.append(consulta)
            if len(self.consultas) <= fallan:
                raise FuenteError(f"wallapop: HTTP 500 para {consulta}")
            return []
    return _F()


class BotFalso:
    """Registra los envíos. `fallos` = cuántos envíos lanzan una excepción antes de funcionar; el texto va en la excepción."""

    def __init__(self, fallos=0):
        self.enviados, self.fallos = [], fallos

    def send_message(self, chat_id, text, **kwargs):
        if self.fallos > 0:
            self.fallos -= 1
            raise ConnectionError(f"Telegram caído ({text})")
        self.enviados.append((chat_id, text))


class ClienteFalso:
    """Con la forma de la respuesta de `anthropic.Anthropic().messages.create` para una tool forzada."""

    def __init__(self, elegidos=None, mejor_id=None, entrada=None, error=None,
                 tokens_in=1200, tokens_out=150, stop_reason="tool_use", sin_tool=False):
        self.llamadas = []
        self._elegidos, self._mejor_id, self._entrada = elegidos or [], mejor_id, entrada
        self.error, self.tokens_in, self.tokens_out = error, tokens_in, tokens_out
        self.stop_reason, self.sin_tool = stop_reason, sin_tool
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.llamadas.append(kwargs)
        if self.error:
            raise self.error
        contenido = [SimpleNamespace(type="text", text="no uso la tool")] if self.sin_tool else [SimpleNamespace(
            type="tool_use", name="informe_vigilancia",
            input=self._entrada if self._entrada is not None else
            {"elegidos": self._elegidos, **({"mejor_id": self._mejor_id} if self._mejor_id is not None else {})})]
        return SimpleNamespace(content=contenido, stop_reason=self.stop_reason,
                               usage=SimpleNamespace(input_tokens=self.tokens_in, output_tokens=self.tokens_out))
