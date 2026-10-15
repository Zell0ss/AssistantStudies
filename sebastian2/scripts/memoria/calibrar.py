"""Calibracion de los umbrales del catalogo (fase 2, H1, D35). Uso (desde sebastian2/):

    python -m scripts.memoria.calibrar [--salida FICHERO]

**[API, OpenAI, menos de 0,01 $]**: embebe las descripciones del catalogo (atributos semilla de la
BD mas `catalogo_extra` del fichero) y las ~30 expresiones de `tests/golden/calibracion_catalogo.yaml`.
No escribe en Qdrant (usa un Qdrant en memoria, mismo coseno) ni en la BD. Saca, por cada expresion,
la puntuacion de la mejor candidata y el margen con la segunda, y por cada umbral de 0,50 a 0,90 en
pasos de 0,05, cuantas positivas acepta y cuantas negativas deja pasar. **Los umbrales los fija el
arquitecto**; este script solo mide.
"""
import argparse
from pathlib import Path

import yaml

from core.memoria.catalogo import Catalogo

FICHERO = Path(__file__).resolve().parent.parent.parent / "tests" / "golden" / "calibracion_catalogo.yaml"
UMBRALES = [round(0.50 + 0.05 * i, 2) for i in range(9)]


def evaluar(pares: dict, catalogo: Catalogo) -> list[dict]:
    """Puntua cada expresion contra el catalogo. `acierta`: la mejor es la esperada (solo positivas)."""
    resultados = []
    for clase, clave in (("positiva", "positivas"), ("negativa", "negativas")):
        for par in pares.get(clave, []):
            candidatos = catalogo.buscar_atributos(par["expresion"], k=3)
            mejor = candidatos[0] if candidatos else {"nombre": None, "score": 0.0}
            segunda = candidatos[1] if len(candidatos) > 1 else {"nombre": None, "score": 0.0}
            resultados.append({
                **par, "clase": clase,
                "mejor": mejor["nombre"], "segunda": segunda["nombre"],
                "score": mejor["score"], "margen": mejor["score"] - segunda["score"],
                "acierta": clase == "positiva" and mejor["nombre"] == par["esperado"],
            })
    return resultados


def tabla_umbrales(resultados: list[dict], margen: float) -> list[dict]:
    """Por umbral: positivas aceptadas (mejor correcta y puntuacion >= umbral) y negativas que pasan
    (puntuacion >= umbral, sea cual sea la candidata), solas y exigiendo ademas `margen`."""
    positivas = [r for r in resultados if r["clase"] == "positiva"]
    negativas = [r for r in resultados if r["clase"] == "negativa"]
    filas = []
    for t in UMBRALES:
        ok = [r for r in positivas if r["acierta"] and r["score"] >= t]
        pasan = [r for r in negativas if r["score"] >= t]
        filas.append({
            "umbral": t,
            "positivas": len(ok),
            "negativas": len(pasan),
            "positivas_con_margen": sum(1 for r in ok if r["margen"] >= margen),
            "negativas_con_margen": sum(1 for r in pasan if r["margen"] >= margen),
        })
    return filas


def texto_informe(resultados: list[dict], margen: float) -> str:
    n_pos = sum(1 for r in resultados if r["clase"] == "positiva")
    n_neg = len(resultados) - n_pos
    lineas = [
        f"### Umbral de puntuacion ({n_pos} positivas, {n_neg} negativas; margen exigido {margen})",
        "",
        "| umbral | positivas aceptadas | negativas que pasan | pos. con margen | neg. con margen |",
        "|---|---|---|---|---|",
    ]
    for f in tabla_umbrales(resultados, margen):
        lineas.append(f"| {f['umbral']:.2f} | {f['positivas']}/{n_pos} | {f['negativas']}/{n_neg} |"
                      f" {f['positivas_con_margen']}/{n_pos} | {f['negativas_con_margen']}/{n_neg} |")
    lineas += ["", "### Detalle", "",
               "| clase | expresion | esperada / parecida a | mejor | puntuacion | segunda | margen |",
               "|---|---|---|---|---|---|---|"]
    for r in resultados:
        objetivo = r.get("esperado") or r.get("parecida_a")
        marca = "" if r["clase"] == "negativa" or r["acierta"] else " ✗"
        lineas.append(f"| {r['clase']} | {r['expresion']} | {objetivo} | {r['mejor']}{marca} |"
                      f" {r['score']:.3f} | {r['segunda']} | {r['margen']:.3f} |")
    return "\n".join(lineas) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salida", help="guarda el informe en este fichero ademas de imprimirlo")
    args = parser.parse_args(argv)

    from core.memoria.ajustes import umbrales
    from core.memoria.embedder import OpenAIEmbedder
    from core.memoria.repositorio import RepositorioMemoria
    from db.connection import close_connection, get_connection
    from qdrant_client import QdrantClient
    from scripts.memoria.crear_colecciones import crear_colecciones
    from utils.config import get_config

    config = get_config()
    pares = yaml.safe_load(FICHERO.read_text())
    try:
        semillas = RepositorioMemoria(get_connection()).listar_atributos(estado="activo")
    finally:
        close_connection()
    extras = [
        {"id": 10_000 + i, "estado": "activo", **e} for i, e in enumerate(pares.get("catalogo_extra", []))
    ]

    cliente = QdrantClient(":memory:")
    crear_colecciones(cliente, "calibracion")
    catalogo = Catalogo(None, OpenAIEmbedder(config["openai_apikey"]), cliente, "calibracion")
    catalogo.indexar_atributos(semillas + extras)

    margen = umbrales(config)["reutilizar"]["margen"]
    informe = texto_informe(evaluar(pares, catalogo), margen)
    print(informe)
    if args.salida:
        Path(args.salida).write_text(informe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
