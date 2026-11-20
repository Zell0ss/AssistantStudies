"""Goldens de H1j (fase 4, D74, R25): con historial, ¿el planner llama a `search_memory` en las consultas? Uso (desde sebastian2/):

    python -m scripts.memoria.golden_consultas [--tope 0.10]

**[API, Anthropic, Haiku 4.5, tope 0,10 $]**. Planner real (prompt, tools, modelo y techo de producción) con un índice de memoria
inventado y un historial inventado de 6 intercambios. No cambia el código de producto, no escribe en la BD ni manda nada a Telegram.

- G1 «¿Qué datos tienes de mí en Telegram?», G2 «¿Cuál es mi id de Telegram?» y G3 «¿Qué sabes de Paco?»: tienen que llamar a
  `search_memory`, aunque el historial ya traiga el dato. 2 pasadas cada una.
- G4 «Recuerda que mi color favorito es el verde»: tiene que seguir llamando a `mark_as_memorable` (D43). 1 pasada.
- G5 «¿Qué tiempo hace en Madrid?»: **no** tiene que llamar a `search_memory`. 1 pasada.

Criterio: 6/6 en G1–G3 y 2/2 en los controles (8 llamadas). Se detiene antes de una llamada si el gasto acumulado más el coste de la
última pasaría del tope. Los datos son inventados (id, usuario, Paco, su alergia).
"""
import argparse
import sys

from core.orchestrator import _MODELO_PLANNER, _PLANNER_EXTRA, _PLANNER_MAX_TOKENS, _PLANNER_TOOLS, _planner_system
from scripts.memoria.diagnostico_identificadores import Presupuesto

# Índices inventados con la forma del real (`indice_memoria`).
_CABECERA = "Lo que me consta de ti (nombres, sin valores; usa search_memory para los valores):"
INDICE_YO = f"{_CABECERA}\n- yo (tú): telegram_id, nota"
INDICE_YO_Y_PACO = f"{INDICE_YO}\n- Paco (persona): alergia"


def _historial(*intercambios):
    mensajes = []
    for usuario, asistente in intercambios:
        mensajes += [{"role": "user", "content": usuario}, {"role": "assistant", "content": asistente}]
    return mensajes


# 6 intercambios en los que el asistente ya ha dicho el valor, como en la traza de producción.
HISTORIAL_ID = _historial(
    ("Hola, Sebastian", "Buenos días, señor."),
    ("Recuerda que mi id de Telegram es 700111222", "Anotado, señor: su id de Telegram es 700111222."),
    ("¿Qué hora es?", "Son las diez y diez, señor."),
    ("¿Cuál es mi id de Telegram?", "Su telegram_id es 700111222, señor."),
    ("Gracias", "A su servicio, señor."),
    ("Perfecto", "Muy bien, señor."),
)
HISTORIAL_PACO = _historial(
    ("Hola, Sebastian", "Buenos días, señor."),
    ("Recuerda que Paco es alérgico a los frutos secos", "Anotado, señor: Paco es alérgico a los frutos secos."),
    ("¿Qué hora es?", "Son las diez y diez, señor."),
    ("¿Qué sabes de Paco?", "Paco es alérgico a los frutos secos, señor."),
    ("Gracias", "A su servicio, señor."),
    ("Perfecto", "Muy bien, señor."),
)

# (nombre, mensaje, índice, historial, tool esperada, tool prohibida, pasadas)
ESCENARIOS = (
    ("G1", "¿Qué datos tienes de mí en Telegram?", INDICE_YO, HISTORIAL_ID, "search_memory", None, 2),
    ("G2", "¿Cuál es mi id de Telegram?", INDICE_YO, HISTORIAL_ID, "search_memory", None, 2),
    ("G3", "¿Qué sabes de Paco?", INDICE_YO_Y_PACO, HISTORIAL_PACO, "search_memory", None, 2),
    ("G4", "Recuerda que mi color favorito es el verde", INDICE_YO, HISTORIAL_ID, "mark_as_memorable", None, 1),
    ("G5", "¿Qué tiempo hace en Madrid?", INDICE_YO, HISTORIAL_ID, None, "search_memory", 1),
)


def llamar_planner(cliente, mensaje: str, indice: str, historial: list):
    return cliente.messages.create(
        model=_MODELO_PLANNER, max_tokens=_PLANNER_MAX_TOKENS, system=_planner_system(indice), tools=_PLANNER_TOOLS,
        messages=historial + [{"role": "user", "content": mensaje}], **_PLANNER_EXTRA)


def evaluar(respuesta, esperada: str | None, prohibida: str | None) -> tuple:
    """(acierta, tools que llamó con su entrada, texto libre, stop_reason)."""
    tools = [{"tool": b.name, "input": b.input} for b in respuesta.content if getattr(b, "type", None) == "tool_use"]
    nombres = {t["tool"] for t in tools}
    acierta = (esperada is None or esperada in nombres) and (prohibida is None or prohibida not in nombres)
    texto = " ".join(b.text for b in respuesta.content if getattr(b, "type", None) == "text").strip()
    return acierta, tools, texto, respuesta.stop_reason


def correr(cliente, tope: float = 0.10) -> dict:
    """Una fila por pasada, en el orden de `ESCENARIOS`. Devuelve `{"filas": [...], "gastado": x, "parada": ...}`."""
    presupuesto = Presupuesto(tope)
    filas, parada = [], None
    for nombre, mensaje, indice, historial, esperada, prohibida, pasadas in ESCENARIOS:
        for n in range(1, pasadas + 1):
            if not presupuesto.cabe("planner"):
                parada = f"tope de {tope:.3f} $ antes de {nombre} pasada {n}"
                break
            respuesta = llamar_planner(cliente, mensaje, indice, historial)
            acierta, tools, texto, parada_api = evaluar(respuesta, esperada, prohibida)
            filas.append({"escenario": nombre, "pasada": n, "mensaje": mensaje, "acierta": acierta, "tools": tools,
                          "texto": texto, "stop_reason": parada_api, "coste": presupuesto.anotar("planner", respuesta)})
        if parada:
            break
    return {"filas": filas, "gastado": presupuesto.gastado, "parada": parada}


def resumen(salida: dict) -> dict:
    """Aciertos de G1–G3 (de 6) y de los controles (de 2); `aprobado` si 6/6 y 2/2 con las 8 llamadas hechas."""
    filas = salida["filas"]
    consultas = [f for f in filas if f["escenario"] in ("G1", "G2", "G3")]
    controles = [f for f in filas if f["escenario"] in ("G4", "G5")]
    return {"consultas": (sum(f["acierta"] for f in consultas), len(consultas)),
            "controles": (sum(f["acierta"] for f in controles), len(controles)),
            "aprobado": len(consultas) == 6 and len(controles) == 2 and all(f["acierta"] for f in filas)}


def detalle(salida: dict) -> str:
    lineas = [f"Planner · {_MODELO_PLANNER}"]
    for f in salida["filas"]:
        llamadas = ", ".join(f"{t['tool']}({t['input']})" for t in f["tools"]) or "ninguna tool"
        lineas.append(f"[{f['escenario']} · pasada {f['pasada']}] {'ACIERTA' if f['acierta'] else 'FALLA'} · «{f['mensaje']}» → "
                      f"{llamadas} · stop={f['stop_reason']} · {f['coste']:.4f} $")
        if f["texto"]:
            lineas.append(f"    texto libre: {f['texto']}")
    r = resumen(salida)
    lineas.append(f"\nG1–G3: {r['consultas'][0]}/{r['consultas'][1]} · controles: {r['controles'][0]}/{r['controles'][1]} · "
                  f"{'APROBADO' if r['aprobado'] else 'NO APROBADO'}")
    if salida["parada"]:
        lineas.append(f"PARADA: {salida['parada']}")
    lineas.append(f"Gasto total: {salida['gastado']:.4f} $ · llamadas: {len(salida['filas'])}")
    return "\n".join(lineas)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Goldens de H1j: consultas con historial (gasta API).")
    parser.add_argument("--tope", type=float, default=0.10)
    args = parser.parse_args(argv)
    from anthropic import Anthropic
    from utils.config import get_config
    cliente = Anthropic(api_key=get_config()["anthropic_apikey"], timeout=60.0)
    print(detalle(correr(cliente, args.tope)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
