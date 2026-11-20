# modules/vigilancias/anuncio.py
"""El anuncio, común a todas las fuentes (fase 4, plan §2.2), y el error de una fuente."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


class FuenteError(Exception):
    """Una consulta no se pudo hacer. El mensaje lleva el código o la clase del fallo y NUNCA el cuerpo de la respuesta
    ni la consulta (D42)."""


@dataclass(frozen=True)
class Anuncio:
    fuente: str               # 'wallapop'
    id: str                   # id de la fuente
    titulo: str
    descripcion: str
    precio: Optional[Decimal]
    moneda: str               # 'EUR'
    ciudad: Optional[str]
    url: str                  # Wallapop: https://es.wallapop.com/item/<web_slug>
    modificado: datetime      # hora local naive, como `events`
    reservado: bool
    envio: Optional[bool]
    vendedor: Optional[str]   # user_id de la fuente
