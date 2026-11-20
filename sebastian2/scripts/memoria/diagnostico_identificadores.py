"""Diagnóstico H1c (fase 4): ¿por qué la memoria no guarda un id de Telegram ni un usuario? Uso (desde sebastian2/):

    python -m scripts.memoria.diagnostico_identificadores [--tope 0.05]

**[API, Anthropic, Haiku 4.5, tope 0,05 $]**. No cambia el código de producto, no escribe en la BD ni manda nada a Telegram.

1. El planner real (`_planner_system`, `_PLANNER_TOOLS`, modelo y techo de producción) recibe una frase con un id y un usuario
   inventados, 2 veces. Se apunta el `texto` que manda a `mark_as_memorable` (hipótesis A: ¿pierde el dato?).
2. El extractor real (prompt, tool y modelo de producción, con un catálogo inventado de la forma del real) recibe el `texto` del
   planner y cuatro frases con identificadores inventados, más un control («color favorito»). Se guarda `bloque.input` tal como
   llega, sin validar, y aparte lo que dejaría pasar `_validar` (hipótesis B: ¿el extractor no guarda identificadores?).

Máximo 12 llamadas (2 del planner y 10 del extractor). Se detiene antes de una llamada si el gasto acumulado más el coste de la
última del mismo tipo pasaría del tope.
"""
import argparse
import json
import sys
from datetime import date

from core.memoria import extractor as ext
from core.orchestrator import (
    _MODELO_PLANNER, _PLANNER_EXTRA, _PLANNER_MAX_TOKENS, _PLANNER_TOOLS, _planner_system,
)

# Haiku 4.5, USD por millón de tokens (skill claude-api): entrada, salida; la escritura de caché cuesta 1,25× y la lectura 0,1×.
PRECIO_ENTRADA, PRECIO_SALIDA = 1.0, 5.0
MAX_LLAMADAS_PLANNER, MAX_LLAMADAS_EXTRACTOR = 2, 10

# Todo inventado (id, usuario, matrícula, socio).
FRASE_PLANNER = "Recuerda que en Telegram mi id es 700111222 y mi usuario es @usuario_prueba"
CASOS = (
    ("id", "Mi id de Telegram es 700111222"),
    ("usuario", "Mi usuario de Telegram es @usuario_prueba"),
    ("matricula", "La matrícula de mi coche es 1234 ABC"),
    ("socio", "Mi número de socio del gimnasio es 55821"),
    ("control", "Mi color favorito es el verde"),
)

# Catálogo inventado con la forma del que ve el extractor (`Servicio.texto_catalogo`): la entidad `yo` y los atributos semilla
# de la migración 011 (los que ve cualquier usuario recién estrenado).
CATALOGO = """Entidades del usuario:
- yo (es el propio usuario)

Atributos:
- nota [*, varios]: Cualquier dato suelto que hay que recordar y no encaja en otra categoria
- alergia [persona, varios]: Sustancia o alimento que a una persona le provoca alergia o intolerancia
- cumpleanos [persona, uno]: Fecha en la que cumple años una persona
- parentesco [persona, varios]: Relacion familiar o de amistad de una persona con el usuario
- preferencia [*, varios]: Gusto, preferencia o manera favorita de hacer algo
- estado [proyecto, uno]: Fase o situacion actual de un proyecto de software
- host [proyecto, uno]: Maquina o servidor donde se ejecuta un proyecto
- stack [proyecto, uno]: Lenguajes, librerias y tecnologias con las que esta hecho un proyecto
- repo [proyecto, uno]: Repositorio de codigo donde vive un proyecto
- db [proyecto, uno]: Base de datos que usa un proyecto"""
INDICE_PLANNER = ("Lo que me consta de ti (nombres, sin valores; usa search_memory para los valores):\n"
                  "- yo (tú): preferencia")


def coste(respuesta) -> float:
    u = getattr(respuesta, "usage", None)
    if u is None:
        return 0.0
    entrada = (getattr(u, "input_tokens", 0) or 0) + 1.25 * (getattr(u, "cache_creation_input_tokens", 0) or 0) \
        + 0.1 * (getattr(u, "cache_read_input_tokens", 0) or 0)
    return (entrada * PRECIO_ENTRADA + (getattr(u, "output_tokens", 0) or 0) * PRECIO_SALIDA) / 1_000_000


class Presupuesto:
    """Gasto acumulado y tope. `cabe(tipo)`: ¿otra llamada de ese tipo, con el coste de la última, sigue dentro del tope?"""

    def __init__(self, tope: float):
        self.tope, self.gastado, self._ultimo = tope, 0.0, {}

    def cabe(self, tipo: str) -> bool:
        return self.gastado + self._ultimo.get(tipo, 0.0) <= self.tope

    def anotar(self, tipo: str, respuesta) -> float:
        c = coste(respuesta)
        self.gastado += c
        self._ultimo[tipo] = c
        return c


def llamar_planner(cliente, frase: str):
    return cliente.messages.create(
        model=_MODELO_PLANNER, max_tokens=_PLANNER_MAX_TOKENS, system=_planner_system(INDICE_PLANNER),
        tools=_PLANNER_TOOLS, messages=[{"role": "user", "content": frase}], **_PLANNER_EXTRA)


def llamar_extractor(cliente, texto: str):
    return cliente.messages.create(
        model=ext.MODELO_EXTRACTOR, max_tokens=ext._TOKENS_MAXIMOS, system=ext._prompt(CATALOGO, date.today()),
        tools=[ext.TOOL_REGISTRAR_HECHOS], tool_choice={"type": "tool", "name": ext.TOOL_REGISTRAR_HECHOS["name"]},
        messages=[{"role": "user", "content": texto}])


def resumen_planner(respuesta) -> dict:
    """Qué hizo el planner: sus tools con su entrada tal cual, el texto que escribió (si lo hay) y por qué paró."""
    tools = [{"tool": b.name, "input": b.input} for b in respuesta.content if getattr(b, "type", None) == "tool_use"]
    texto = " ".join(b.text for b in respuesta.content if getattr(b, "type", None) == "text").strip()
    memorables = [t["input"].get("texto") for t in tools if t["tool"] == "mark_as_memorable"]
    return {"stop_reason": respuesta.stop_reason, "tools": tools, "texto_libre": texto, "texto_memorable": memorables}


def resumen_extractor(respuesta) -> dict:
    """`bloque.input` tal como llega y lo que dejaría pasar `_validar` (la lista que usaría el servicio)."""
    bloque = next((b for b in respuesta.content
                   if getattr(b, "type", None) == "tool_use" and b.name == ext.TOOL_REGISTRAR_HECHOS["name"]), None)
    if bloque is None:
        return {"stop_reason": respuesta.stop_reason, "input": None, "validados": []}
    crudos = (bloque.input or {}).get("hechos") or []
    return {"stop_reason": respuesta.stop_reason, "input": bloque.input,
            "validados": [h for h in map(ext._validar, crudos) if h][:ext.MAX_HECHOS]}


def correr(cliente, tope: float = 0.05) -> dict:
    """Planner ×2, luego el extractor: una pasada por caso (el `texto` del planner primero) y, con lo que quede de las 10
    llamadas, una segunda pasada en el mismo orden. Devuelve `{"planner": [...], "extractor": [...], "gastado": x, "parada": ...}`."""
    presupuesto = Presupuesto(tope)
    salida = {"planner": [], "extractor": [], "gastado": 0.0, "parada": None}
    for n in range(1, MAX_LLAMADAS_PLANNER + 1):
        if not presupuesto.cabe("planner"):
            salida["parada"] = f"tope de {tope:.3f} $ antes de la llamada {n} del planner"
            break
        r = llamar_planner(cliente, FRASE_PLANNER)
        salida["planner"].append({"pasada": n, "coste": presupuesto.anotar("planner", r), **resumen_planner(r)})
    textos = [t for p in salida["planner"] for t in p["texto_memorable"] if t]
    casos = [("planner", textos[0])] if textos else []
    casos += list(CASOS)
    pendientes = [(nombre, texto, 1) for nombre, texto in casos] + [(nombre, texto, 2) for nombre, texto in casos]
    for nombre, texto, pasada in pendientes[:MAX_LLAMADAS_EXTRACTOR]:
        if not presupuesto.cabe("extractor"):
            parada = f"tope de {tope:.3f} $ antes de {nombre} pasada {pasada}"
            salida["parada"] = f"{salida['parada']}; {parada}" if salida["parada"] else parada
            break
        r = llamar_extractor(cliente, texto)
        salida["extractor"].append({"caso": nombre, "pasada": pasada, "texto": texto,
                                    "coste": presupuesto.anotar("extractor", r), **resumen_extractor(r)})
    salida["gastado"] = presupuesto.gastado
    return salida


def detalle(salida: dict) -> str:
    j = lambda x: json.dumps(x, ensure_ascii=False)       # noqa: E731
    lineas = [f"Planner · {_MODELO_PLANNER} · frase: «{FRASE_PLANNER}»"]
    for p in salida["planner"]:
        lineas.append(f"  pasada {p['pasada']} · stop={p['stop_reason']} · {p['coste']:.4f} $")
        lineas += [f"    tool {t['tool']}: {j(t['input'])}" for t in p["tools"]]
        if p["texto_libre"]:
            lineas.append(f"    texto libre: {p['texto_libre']}")
    lineas.append(f"\nExtractor · {ext.MODELO_EXTRACTOR}")
    for e in salida["extractor"]:
        lineas.append(f"  [{e['caso']} · pasada {e['pasada']}] «{e['texto']}» · stop={e['stop_reason']} · {e['coste']:.4f} $")
        lineas.append(f"    bloque.input: {j(e['input'])}")
        lineas.append(f"    pasan _validar: {len(e['validados'])}" + (f" → {j(e['validados'])}" if e["validados"] else ""))
    if salida["parada"]:
        lineas.append(f"\nPARADA: {salida['parada']}")
    lineas.append(f"\nGasto total: {salida['gastado']:.4f} $ · llamadas: planner {len(salida['planner'])}, "
                  f"extractor {len(salida['extractor'])}")
    return "\n".join(lineas)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico H1c: memoria e identificadores (gasta API).")
    parser.add_argument("--tope", type=float, default=0.05)
    args = parser.parse_args(argv)
    from anthropic import Anthropic
    from utils.config import get_config
    cliente = Anthropic(api_key=get_config()["anthropic_apikey"], timeout=60.0)
    print(detalle(correr(cliente, args.tope)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
