"""Goldens del juez de vigilancias (fase 4, H1, plan §3 [API]). Uso (desde sebastian2/):

    python -m scripts.vigilancias.golden_juez <vigilancia.yaml> [--pasadas 3] [--tope 0.30]

**[API, Anthropic, tope 0,30 $]**: juzga los 12 anuncios inventados de `tests/golden/vigilancias/anuncios.yaml` con las reglas del
YAML de Josem, `--pasadas` veces con `claude-haiku-4-5-20251001` y otras tantas con `claude-haiku-5-5` (esta, con
`effort: low` y sin thinking, como pide el plan). Informa de aciertos (criterio de `criterios.py`), latencia y coste por modelo.
Se detiene si el gasto acumulado pasa de `--tope`. No escribe en la BD ni manda nada a Telegram.
"""
import argparse
import sys
import time
from pathlib import Path

import yaml

from modules.vigilancias.juez import JuezError, juzgar
from modules.vigilancias.repositorio import validar
from tests.golden.vigilancias.criterios import cargar_anuncios, evaluar

MODELOS = ("claude-haiku-4-5-20251001", "claude-haiku-5-5")


def correr(cliente, reglas: str, pasadas: int = 3, tope: float = 0.30, modelos=MODELOS, reloj=time.monotonic) -> list:
    """Una fila por pasada: modelo, número, acierto, fallos, latencia, tokens, coste, y lo que eligió el juez. Corta si se pasa el tope."""
    anuncios = cargar_anuncios()
    candidatos = [a for a, _, _ in anuncios]
    filas, gastado = [], 0.0
    for modelo in modelos:
        for n in range(1, pasadas + 1):
            if gastado >= tope:
                filas.append({"modelo": modelo, "pasada": n, "error": f"tope de {tope:.2f} $ alcanzado ({gastado:.4f} $)"})
                continue
            inicio = reloj()
            try:
                informe = juzgar(cliente, reglas, candidatos, modelo)
            except JuezError as e:
                filas.append({"modelo": modelo, "pasada": n, "error": str(e), "latencia": reloj() - inicio})
                continue
            acierta, fallos = evaluar(informe, anuncios)
            gastado += informe.coste_usd
            filas.append({"modelo": modelo, "pasada": n, "acierta": acierta, "fallos": fallos, "latencia": reloj() - inicio,
                          "tokens_in": informe.tokens_in, "tokens_out": informe.tokens_out, "coste": informe.coste_usd,
                          "elegidos": informe.elegidos, "cierre": informe.cierre})
    return filas


def resumen(filas: list) -> str:
    lineas = []
    for modelo in dict.fromkeys(f["modelo"] for f in filas):
        suyas = [f for f in filas if f["modelo"] == modelo]
        buenas = [f for f in suyas if "error" not in f]
        aciertos = sum(f["acierta"] for f in buenas)
        latencia = sum(f["latencia"] for f in buenas) / len(buenas) if buenas else float("nan")
        coste = sum(f["coste"] for f in buenas)
        lineas.append(f"{modelo}: aciertos {aciertos}/{len(suyas)}  latencia media {latencia:.1f} s  coste {coste:.4f} $ "
                      f"({coste / len(buenas) if buenas else 0:.4f} $ por pasada)  errores {len(suyas) - len(buenas)}")
    return "\n".join(lineas)


def detalle(filas: list) -> str:
    lineas = []
    for f in filas:
        cabecera = f"[{f['modelo']} · pasada {f['pasada']}]"
        if "error" in f:
            lineas.append(f"{cabecera} ERROR: {f['error']}")
            continue
        lineas.append(f"{cabecera} {'ACIERTA' if f['acierta'] else 'FALLA'}  {f['latencia']:.1f} s  "
                      f"in={f['tokens_in']} out={f['tokens_out']}  {f['coste']:.4f} $")
        lineas += [f"    ✗ {x}" for x in f["fallos"]]
        lineas += [f"    {e['id']} {e['semaforo']}: {e['texto']}" for e in f["elegidos"]]
        lineas.append(f"    cierre: {f['cierre']}")
    return "\n".join(lineas)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Goldens del juez de vigilancias (gasta API).")
    parser.add_argument("fichero", type=Path)
    parser.add_argument("--pasadas", type=int, default=3)
    parser.add_argument("--tope", type=float, default=0.30)
    args = parser.parse_args(argv)
    from anthropic import Anthropic
    from utils.config import get_config
    reglas = validar(yaml.safe_load(args.fichero.read_text(encoding="utf-8")))["reglas"]
    cliente = Anthropic(api_key=get_config()["anthropic_apikey"], timeout=60.0)
    filas = correr(cliente, reglas, args.pasadas, args.tope)
    print(detalle(filas))
    print("\n" + resumen(filas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
