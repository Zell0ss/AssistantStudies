"""H1 (fase 2): la maquinaria de calibracion (sin API: EmbedderFalso, Qdrant en memoria)."""
from pathlib import Path

import yaml

from scripts.memoria.calibrar import evaluar, tabla_umbrales, texto_informe
from core.memoria.catalogo import Catalogo
from scripts.memoria.crear_colecciones import crear_colecciones
from tests.fakes_memoria import EmbedderFalso, qdrant_en_memoria

FICHERO = Path(__file__).parent / "golden" / "calibracion_catalogo.yaml"
ATRIBUTOS = [
    {"id": 1, "nombre": "alergia", "estado": "activo", "descripcion": "alergia a un alimento o sustancia"},
    {"id": 2, "nombre": "matricula", "estado": "activo", "descripcion": "matricula placa de un vehiculo"},
]


def _catalogo():
    cliente = qdrant_en_memoria()
    crear_colecciones(cliente, "cal_test")
    cat = Catalogo(None, EmbedderFalso(), cliente, "cal_test")
    cat.indexar_atributos(ATRIBUTOS)
    return cat


def test_fichero_de_calibracion_tiene_15_y_15():
    datos = yaml.safe_load(FICHERO.read_text())
    assert len(datos["positivas"]) == 15
    assert len(datos["negativas"]) == 15
    assert all({"expresion", "esperado"} <= set(p) for p in datos["positivas"])
    assert all({"expresion", "parecida_a"} <= set(n) for n in datos["negativas"])


def test_evaluar_saca_puntuacion_margen_y_acierto():
    pares = {"positivas": [{"expresion": "alergia a un alimento", "esperado": "alergia"}],
             "negativas": [{"expresion": "zzz qqq", "parecida_a": "matricula"}]}

    resultados = evaluar(pares, _catalogo())

    pos, neg = resultados
    assert pos["clase"] == "positiva" and pos["mejor"] == "alergia" and pos["acierta"]
    assert pos["score"] > 0.5 and pos["margen"] > 0
    assert neg["clase"] == "negativa" and neg["score"] < 0.1


def test_tabla_cuenta_positivas_aceptadas_y_negativas_que_pasan():
    resultados = [
        {"clase": "positiva", "acierta": True, "score": 0.80, "margen": 0.20},
        {"clase": "positiva", "acierta": True, "score": 0.60, "margen": 0.01},
        {"clase": "positiva", "acierta": False, "score": 0.90, "margen": 0.30},  # top1 equivocado
        {"clase": "negativa", "acierta": False, "score": 0.70, "margen": 0.10},
        {"clase": "negativa", "acierta": False, "score": 0.40, "margen": 0.10},
    ]

    filas = {f["umbral"]: f for f in tabla_umbrales(resultados, margen=0.05)}

    assert sorted(filas) == [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]
    assert (filas[0.5]["positivas"], filas[0.5]["negativas"]) == (2, 1)
    assert (filas[0.6]["positivas"], filas[0.6]["negativas"]) == (2, 1)
    assert (filas[0.7]["positivas"], filas[0.7]["negativas"]) == (1, 1)
    assert (filas[0.85]["positivas"], filas[0.85]["negativas"]) == (0, 0)
    # con el margen exigido, la positiva de margen 0.01 ya no cuenta
    assert filas[0.6]["positivas_con_margen"] == 1
    assert filas[0.5]["negativas_con_margen"] == 1


def test_informe_incluye_la_tabla_y_el_detalle():
    resultados = [
        {"clase": "positiva", "expresion": "a", "esperado": "x", "mejor": "x", "segunda": "y",
         "acierta": True, "score": 0.8, "margen": 0.2},
        {"clase": "negativa", "expresion": "b", "parecida_a": "x", "mejor": "x", "segunda": "y",
         "acierta": False, "score": 0.4, "margen": 0.1},
    ]
    informe = texto_informe(resultados, margen=0.05)
    assert "| umbral |" in informe and "| 0.75 |" in informe
    assert "a" in informe and "b" in informe
