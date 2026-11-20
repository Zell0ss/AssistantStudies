"""Humo real de Wallapop (fase 4, H1, [RED], D64). Uso (desde sebastian2/):

    python -m scripts.vigilancias.humo_wallapop <vigilancia.yaml>

**[RED], gratis, sin LLM, sin BD**: lanza cada consulta del YAML UNA vez contra la API real (una petición por consulta, con una
pausa de un segundo) y cuenta, por consulta: cuántos anuncios devolvió, cuántos son nuevos (modificados en las últimas 48 h,
sin mirar vistos) y cuántos de esos pasan el filtro. Después comprueba que los campos que el parser asume existen de verdad
(precio, ciudad, `reserved`, `shipping`) y enseña la FORMA del primer item (claves y tipos, nunca valores).

D42: no imprime títulos, descripciones ni las consultas (van por número), ni el cuerpo de ninguna respuesta.
"""
import argparse
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests
import yaml

from modules.vigilancias.anuncio import FuenteError
from modules.vigilancias.filtro import es_nuevo, pasa_filtro
from modules.vigilancias.fuentes.wallapop import Wallapop
from modules.vigilancias.repositorio import validar

PAUSA_S = 1.0


def _forma(valor) -> str:
    """El tipo de un valor JSON y, si es un objeto, el de sus claves: nunca el valor."""
    if isinstance(valor, dict):
        return "{" + ", ".join(f"{k}: {_forma(v)}" for k, v in sorted(valor.items())) + "}"
    return type(valor).__name__


def humo(vigilancia: dict, ahora: datetime, get=requests.get, pausa=PAUSA_S) -> dict:
    """Devuelve el recuento por consulta, los totales sin repetir `id`, la cobertura de campos y la forma del primer item."""
    cuerpos = []

    def get_espia(*args, **kwargs):
        respuesta = get(*args, **kwargs)
        cuerpos.append(respuesta)
        return respuesta

    fuente = Wallapop(get=get_espia)
    por_consulta, todos = [], {}
    for i, consulta in enumerate(vigilancia["consultas"], 1):
        if i > 1:
            time.sleep(pausa)
        try:
            anuncios = fuente.buscar(consulta)
        except FuenteError as e:
            por_consulta.append({"n": i, "error": str(e)})
            continue
        nuevos = [a for a in anuncios if es_nuevo(a, None, ahora)]
        por_consulta.append({"n": i, "devueltos": len(anuncios), "nuevos": len(nuevos),
                             "pasan": sum(pasa_filtro(a, vigilancia["filtros"]) for a in nuevos)})
        todos.update({a.id: a for a in anuncios})
    nuevos = [a for a in todos.values() if es_nuevo(a, None, ahora)]
    forma = None
    for r in cuerpos:
        try:
            primero = r.json()["data"]["section"]["payload"]["items"][0]
            forma = {k: _forma(v) for k, v in sorted(primero.items()) if k in
                     ("id", "title", "description", "price", "location", "web_slug", "modified_at", "reserved", "shipping", "user_id")}
            break
        except (ValueError, KeyError, IndexError, TypeError):
            continue
    edades = sorted((ahora - a.modificado).total_seconds() / 3600 for a in todos.values())
    return {
        "por_consulta": por_consulta,
        "unicos": len(todos), "nuevos": len(nuevos), "pasan": sum(pasa_filtro(a, vigilancia["filtros"]) for a in nuevos),
        "cobertura": {"con_precio": sum(a.precio is not None for a in todos.values()),
                      "con_ciudad": sum(a.ciudad is not None for a in todos.values()),
                      "reservados": sum(a.reservado for a in todos.values()),
                      "envio": dict(Counter(str(a.envio) for a in todos.values()))},
        "edad_horas": {"min": round(edades[0], 1), "mediana": round(edades[len(edades) // 2], 1), "max": round(edades[-1], 1)} if edades else None,
        "forma_primer_item": forma,
    }


def informe(r: dict) -> str:
    lineas = ["consulta  devueltos  nuevos(48h)  pasan_filtro"]
    for c in r["por_consulta"]:
        lineas.append(f"{c['n']:>8}  {c['error']}" if "error" in c else f"{c['n']:>8}  {c['devueltos']:>9}  {c['nuevos']:>11}  {c['pasan']:>12}")
    lineas += [f"únicos (sin repetir id): {r['unicos']}  nuevos: {r['nuevos']}  pasan el filtro: {r['pasan']}",
               f"cobertura de campos: {r['cobertura']}", f"edad del anuncio (h): {r['edad_horas']}"]
    if r["forma_primer_item"]:
        lineas.append("forma del primer item (claves y tipos):")
        lineas += [f"  {k}: {v}" for k, v in r["forma_primer_item"].items()]
    return "\n".join(lineas)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Humo real de Wallapop: 1 petición por consulta, sin LLM ni BD.")
    parser.add_argument("fichero", type=Path)
    args = parser.parse_args(argv)
    vigilancia = validar(yaml.safe_load(args.fichero.read_text(encoding="utf-8")))
    print(informe(humo(vigilancia, datetime.now())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
