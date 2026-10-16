"""Calibracion de los umbrales del catalogo (fase 2, H1, D35). Uso (desde sebastian2/):

    python -m scripts.memoria.calibrar [--salida FICHERO]

**[API, OpenAI, menos de 0,01 $]**: embebe el catalogo (atributos semilla de la BD mas
`catalogo_extra` del fichero) en tres representaciones (a: descripcion; b: nombre: descripcion; c:
descripcion + 3 ejemplos) y las expresiones de `tests/golden/calibracion_catalogo.yaml` (15 positivas,
25 negativas). No escribe en Qdrant (usa un Qdrant en memoria, mismo coseno) ni en la BD. Por cada
representacion saca la puntuacion y el margen de cada expresion y, por umbral de 0,50 a 0,90, cuantas
positivas acepta y cuantas negativas deja pasar. `decidir` aplica la regla de H1-revision §2.2 para
elegir representacion y umbrales; imprime tambien el coste de OpenAI medido.
"""
import argparse
import math
from pathlib import Path

import yaml

from core.memoria.catalogo import REPRESENTACIONES, Catalogo

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


# Orden = de la mas sencilla a la menos: en caso de empate gana la primera (H1-revision §2.2).
ORDEN = ("a", "b", "c")
NOMBRES = {"a": "descripcion", "b": "nombre_descripcion", "c": "con_ejemplos"}
HOLGURA = 0.03


def decidir(por_representacion: dict, total_positivas: int) -> dict:
    """Regla de H1-revision §2.2, sin volver al arquitecto:

    - cada representacion: corte = max(negativas) + 0,03; cuenta las positivas acertadas **por encima** del corte;
    - gana la que mas tiene (empate: la mas sencilla, a < b < c);
    - reutilizar = corte redondeado hacia arriba a 0,01, margen 0,03; sustituir = reutilizar + 0,10, margen 0,05;
    - si ninguna representacion tiene al menos 8 de 15 positivas por encima de su `reutilizar`: parar.
    """
    detalle = {}
    for rep in ORDEN:
        resultados = por_representacion.get(rep)
        if resultados is None:
            continue
        max_neg = max((r["score"] for r in resultados if r["clase"] == "negativa"), default=0.0)
        corte = round(max_neg + HOLGURA, 6)
        reutilizar = math.ceil(round(corte * 100, 6)) / 100
        positivas = [r for r in resultados if r["clase"] == "positiva" and r["acierta"]]
        detalle[rep] = {
            "max_negativas": max_neg, "corte": corte, "reutilizar": reutilizar,
            "sobre_corte": sum(1 for r in positivas if round(r["score"], 6) > corte),
            "sobre_reutilizar": sum(1 for r in positivas if round(r["score"], 6) >= reutilizar),
        }
    mejor = max(detalle, key=lambda r: (detalle[r]["sobre_corte"], -ORDEN.index(r)))
    reutilizar = detalle[mejor]["reutilizar"]
    return {
        "representacion": mejor,
        "umbrales": {
            "reutilizar": {"puntuacion": reutilizar, "margen": 0.03},
            "sustituir": {"puntuacion": round(reutilizar + 0.10, 2), "margen": 0.05},
        },
        "positivas_sobre_corte": {r: d["sobre_corte"] for r, d in detalle.items()},
        "detalle": detalle,
        "total_positivas": total_positivas,
        "parar": all(d["sobre_reutilizar"] < 8 for d in detalle.values()),
    }


def texto_decision(decision: dict) -> str:
    lineas = ["### Regla del §2.2", "",
              "| representacion | max(negativas) | corte (+0,03) | reutilizar | positivas sobre el corte | positivas >= reutilizar |",
              "|---|---|---|---|---|---|"]
    for rep, d in decision["detalle"].items():
        lineas.append(f"| {rep} ({NOMBRES[rep]}) | {d['max_negativas']:.3f} | {d['corte']:.3f} |"
                      f" {d['reutilizar']:.2f} | {d['sobre_corte']}/{decision['total_positivas']} |"
                      f" {d['sobre_reutilizar']}/{decision['total_positivas']} |")
    u = decision["umbrales"]
    lineas += ["", f"**Representacion elegida: {decision['representacion']} ({NOMBRES[decision['representacion']]}).**",
               f"- reutilizar: {u['reutilizar']['puntuacion']:.2f}, margen {u['reutilizar']['margen']}",
               f"- sustituir: {u['sustituir']['puntuacion']:.2f}, margen {u['sustituir']['margen']}"]
    if decision["parar"]:
        lineas += ["", "**PARAR: ninguna representacion tiene 8 de 15 positivas por encima de `reutilizar`.**"]
    return "\n".join(lineas) + "\n"


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


class _EmbedderConCache:
    """Cada texto se embebe una sola vez aunque entre en tres representaciones: asi el coste es el real."""

    def __init__(self, embedder):
        self._embedder = embedder
        self._cache = {}
        self.dimension = embedder.dimension

    def embed(self, textos):
        nuevos = [t for t in dict.fromkeys(textos) if t not in self._cache]
        if nuevos:
            self._cache.update(zip(nuevos, self._embedder.embed(nuevos)))
        return [self._cache[t] for t in textos]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salida", help="guarda el informe en este fichero ademas de imprimirlo")
    args = parser.parse_args(argv)

    from core.memoria.embedder import PRECIO_EMBEDDING_POR_MILLON, OpenAIEmbedder
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
    atributos = [{**a, "ejemplos": pares.get("ejemplos", {}).get(a["nombre"], [])} for a in semillas + extras]

    openai = OpenAIEmbedder(config["openai_apikey"])
    embedder = _EmbedderConCache(openai)
    margen = 0.03  # el margen de `reutilizar` de la regla de H1-revision §2.2
    por_representacion, partes = {}, []
    for clave, representacion in zip(ORDEN, REPRESENTACIONES):
        cliente = QdrantClient(":memory:")
        crear_colecciones(cliente, "calibracion")
        catalogo = Catalogo(None, embedder, cliente, "calibracion")
        catalogo.indexar_atributos(atributos, representacion=representacion)
        resultados = evaluar(pares, catalogo)
        por_representacion[clave] = resultados
        partes.append(f"## Representacion {clave}: {NOMBRES[clave]}\n\n" + texto_informe(resultados, margen))

    decision = decidir(por_representacion, total_positivas=len(pares["positivas"]))
    coste = (f"Coste OpenAI medido: {openai.tokens} tokens x {PRECIO_EMBEDDING_POR_MILLON} $/millon = "
             f"{openai.coste():.6f} $ (Anthropic: 0 $)")
    informe = "\n".join([texto_decision(decision), *partes, coste]) + "\n"
    print(informe)
    if args.salida:
        Path(args.salida).write_text(informe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
