"""Goldens de H1j (fase 4, D74, R25): con historial, ¿el planner llama a `search_memory` en las consultas? Uso (desde sebastian2/):

    python -m scripts.memoria.golden_consultas [--tope 0.10] [--vuelta 1|2]

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

# G2b (segunda vuelta, R25b): otro dato concreto, para ver si la regla generaliza más allá de Telegram.
INDICE_CUMPLE = f"{_CABECERA}\n- yo (tú): cumpleanos, telegram_id, nota"
HISTORIAL_CUMPLE = _historial(
    ("Hola, Sebastian", "Buenos días, señor."),
    ("Recuerda que mi cumpleaños es el 12 de marzo", "Anotado, señor: su cumpleaños es el 12 de marzo."),
    ("¿Qué hora es?", "Son las diez y diez, señor."),
    ("¿Cuándo es mi cumpleaños?", "Su cumpleaños es el 12 de marzo, señor."),
    ("Gracias", "A su servicio, señor."),
    ("Perfecto", "Muy bien, señor."),
)

_G1 = ("G1", "¿Qué datos tienes de mí en Telegram?", INDICE_YO, HISTORIAL_ID, "search_memory", None)
_G2 = ("G2", "¿Cuál es mi id de Telegram?", INDICE_YO, HISTORIAL_ID, "search_memory", None)
_G2B = ("G2b", "¿Cuándo es mi cumpleaños?", INDICE_CUMPLE, HISTORIAL_CUMPLE, "search_memory", None)
_G3 = ("G3", "¿Qué sabes de Paco?", INDICE_YO_Y_PACO, HISTORIAL_PACO, "search_memory", None)
_G4 = ("G4", "Recuerda que mi color favorito es el verde", INDICE_YO, HISTORIAL_ID, "mark_as_memorable", None)
_G5 = ("G5", "¿Qué tiempo hace en Madrid?", INDICE_YO, HISTORIAL_ID, None, "search_memory")

# Primera vuelta: (nombre, mensaje, índice, historial, tool esperada, tool prohibida, pasadas), 8 llamadas.
ESCENARIOS = ((*_G1, 2), (*_G2, 2), (*_G3, 2), (*_G4, 1), (*_G5, 1))
# Segunda vuelta (R25b, H1j-revision): G2 ×2, G2b ×1 (nuevo) y G1, G3 y G4 ×1 (sin regresión), 6 llamadas.
SEGUNDA_VUELTA = ((*_G2, 2), (*_G2B, 1), (*_G1, 1), (*_G3, 1), (*_G4, 1))
# Tercera vuelta (H1j-revision §2, prueba de posición de la frase): G2 ×2, G2b, G1 y G3, 5 llamadas.
TERCERA_VUELTA = ((*_G2, 2), (*_G2B, 1), (*_G1, 1), (*_G3, 1))
VUELTAS = {1: ESCENARIOS, 2: SEGUNDA_VUELTA, 3: TERCERA_VUELTA}


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


def correr(cliente, tope: float = 0.10, vuelta: int = 1) -> dict:
    """Una fila por pasada, en el orden de la vuelta (`VUELTAS`). Devuelve `{"filas": [...], "gastado": x, "parada": ...}`."""
    presupuesto = Presupuesto(tope)
    filas, parada = [], None
    for nombre, mensaje, indice, historial, esperada, prohibida, pasadas in VUELTAS[vuelta]:
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


def resumen_segunda_vuelta(salida: dict) -> dict:
    """Segunda vuelta: aciertos de G2 y G2b (de 3) y de G1, G3 y G4 (de 3, «sin regresión»); `aprobado` si 3/3 y 3/3 con las 6
    llamadas hechas."""
    filas = salida["filas"]
    nuevas = [f for f in filas if f["escenario"] in ("G2", "G2b")]
    previas = [f for f in filas if f["escenario"] in ("G1", "G3", "G4")]
    return {"g2_g2b": (sum(f["acierta"] for f in nuevas), len(nuevas)),
            "sin_regresion": (sum(f["acierta"] for f in previas), len(previas)),
            "aprobado": len(nuevas) == 3 and len(previas) == 3 and all(f["acierta"] for f in filas)}


def resumen_tercera_vuelta(salida: dict, g2_antes: int = 0) -> dict:
    """Prueba de posición: aciertos de G2 (de 2) y de G2b, G1 y G3 (de 3). `se_queda_la_posicion_nueva` si G2 mejora respecto a
    `g2_antes` (0 de 4 entre las dos vueltas anteriores) y las otras tres siguen bien; si no, se vuelve a la posición anterior."""
    filas = salida["filas"]
    g2 = [f for f in filas if f["escenario"] == "G2"]
    otras = [f for f in filas if f["escenario"] in ("G2b", "G1", "G3")]
    aciertos_g2 = sum(f["acierta"] for f in g2)
    completa = len(g2) == 2 and len(otras) == 3
    return {"g2": (aciertos_g2, len(g2)), "otras": (sum(f["acierta"] for f in otras), len(otras)),
            "se_queda_la_posicion_nueva": completa and aciertos_g2 > g2_antes and all(f["acierta"] for f in otras)}


def resumen(salida: dict) -> dict:
    """Aciertos de G1–G3 (de 6) y de los controles (de 2); `aprobado` si 6/6 y 2/2 con las 8 llamadas hechas."""
    filas = salida["filas"]
    consultas = [f for f in filas if f["escenario"] in ("G1", "G2", "G3")]
    controles = [f for f in filas if f["escenario"] in ("G4", "G5")]
    return {"consultas": (sum(f["acierta"] for f in consultas), len(consultas)),
            "controles": (sum(f["acierta"] for f in controles), len(controles)),
            "aprobado": len(consultas) == 6 and len(controles) == 2 and all(f["acierta"] for f in filas)}


def detalle(salida: dict, vuelta: int = 1) -> str:
    lineas = [f"Planner · {_MODELO_PLANNER} · vuelta {vuelta}"]
    for f in salida["filas"]:
        llamadas = ", ".join(f"{t['tool']}({t['input']})" for t in f["tools"]) or "ninguna tool"
        lineas.append(f"[{f['escenario']} · pasada {f['pasada']}] {'ACIERTA' if f['acierta'] else 'FALLA'} · «{f['mensaje']}» → "
                      f"{llamadas} · stop={f['stop_reason']} · {f['coste']:.4f} $")
        if f["texto"]:
            lineas.append(f"    texto libre: {f['texto']}")
    if vuelta == 3:
        r = resumen_tercera_vuelta(salida)
        lineas.append(f"\nG2: {r['g2'][0]}/{r['g2'][1]} · G2b, G1 y G3: {r['otras'][0]}/{r['otras'][1]} · "
                      f"{'SE QUEDA LA POSICIÓN NUEVA' if r['se_queda_la_posicion_nueva'] else 'VUELVE A LA POSICIÓN ANTERIOR'}")
    elif vuelta == 2:
        r = resumen_segunda_vuelta(salida)
        lineas.append(f"\nG2 y G2b: {r['g2_g2b'][0]}/{r['g2_g2b'][1]} · G1, G3 y G4 sin regresión: "
                      f"{r['sin_regresion'][0]}/{r['sin_regresion'][1]} · {'APROBADO' if r['aprobado'] else 'NO APROBADO'}")
    else:
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
    parser.add_argument("--vuelta", type=int, choices=sorted(VUELTAS), default=1,
                        help="1: G1–G5 (8 llamadas); 2: G2 ×2, G2b, G1, G3, G4 (6 llamadas)")
    args = parser.parse_args(argv)
    from anthropic import Anthropic
    from utils.config import get_config
    cliente = Anthropic(api_key=get_config()["anthropic_apikey"], timeout=60.0)
    print(detalle(correr(cliente, args.tope, args.vuelta), args.vuelta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
