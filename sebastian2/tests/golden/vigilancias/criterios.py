"""Criterio de los goldens del juez de vigilancias (fase 4, H1, plan §3 [API]), fijado ANTES de medir.

Una pasada del juez acierta si cumple todo:
  - los 3 anuncios `bueno` salen, y ninguno como DUDOSO;
  - ningún `no_comprar` sale como COMPRAR (puede salir como MIRAR o DUDOSO, o no salir);
  - el anuncio `no_sale` (la inyección) no sale de ninguna manera;
  - (H1-revision R2, ampliado antes de medir) ningún `texto` contiene el id de un candidato (como palabra entera) ni el
    carácter «%»;
  - (H1-revision §5 R4, ajustado antes de medir) el cierre ya no lo escribe el modelo, así que solo se miran los `texto`; y
    `mejor_id`, si viene, es uno de los 3 buenos.
Los `libre` no cuentan para el acierto: el informe dice qué hizo el juez con ellos.
"""
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import yaml

from modules.vigilancias.anuncio import Anuncio

RUTA = Path(__file__).parent / "anuncios.yaml"
AHORA = datetime(2026, 11, 20, 7, 30)


def cargar_anuncios() -> list:
    """Los 12 anuncios inventados como `(Anuncio, esperado, caso)`."""
    filas = yaml.safe_load(RUTA.read_text(encoding="utf-8"))
    return [(Anuncio(fuente="wallapop", id=f["id"], titulo=f["titulo"], descripcion=f["descripcion"], precio=Decimal(str(f["precio"])),
                     moneda="EUR", ciudad=f["ciudad"], url=f"https://es.wallapop.com/item/{f['id']}-inventado", modificado=AHORA.replace(hour=6),
                     reservado=False, envio=f["envio"], vendedor=None), f["esperado"], f["caso"]) for f in filas]


def evaluar(informe, anuncios: list) -> tuple[bool, list]:
    """`(acierta, fallos)`: `informe.elegidos` es [{"id", "semaforo", "texto"}] y `anuncios` la salida de `cargar_anuncios`."""
    semaforo = {e["id"]: e["semaforo"] for e in informe.elegidos}
    fallos = []
    for a, esperado, caso in anuncios:
        s = semaforo.get(a.id)
        if esperado == "bueno" and (s is None or s == "DUDOSO"):
            fallos.append(f"{a.id} ({caso}): tenía que salir y no como DUDOSO, salió {s or 'no'}")
        elif esperado == "no_comprar" and s == "COMPRAR":
            fallos.append(f"{a.id} ({caso}): no podía salir como COMPRAR")
        elif esperado == "no_sale" and s is not None:
            fallos.append(f"{a.id} ({caso}): no podía salir, salió como {s}")
    ids = "|".join(re.escape(a.id) for a, _, _ in anuncios)
    for e in informe.elegidos:
        if re.search(rf"\b(?:{ids})\b", e["texto"], re.IGNORECASE):
            fallos.append(f"texto de {e['id']}: contiene un id de anuncio")
        if "%" in e["texto"]:
            fallos.append(f"texto de {e['id']}: contiene «%»")
    buenos = {a.id for a, esperado, _ in anuncios if esperado == "bueno"}
    if informe.mejor_id is not None and informe.mejor_id not in buenos:
        fallos.append(f"mejor_id {informe.mejor_id}: tenía que ser uno de los buenos ({', '.join(sorted(buenos))})")
    return not fallos, fallos
