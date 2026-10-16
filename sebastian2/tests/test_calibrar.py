"""H1 (fase 2): la maquinaria de calibracion (sin API: EmbedderFalso, Qdrant en memoria)."""
from pathlib import Path

import yaml

from scripts.memoria.calibrar import decidir, evaluar, tabla_umbrales, texto_informe
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


def test_fichero_de_calibracion_tiene_15_y_25():
    datos = yaml.safe_load(FICHERO.read_text())
    assert len(datos["positivas"]) == 15
    assert len(datos["negativas"]) == 25
    nombres = {a for a in datos["ejemplos"]}
    esperados = {p["esperado"] for p in datos["positivas"]}
    assert esperados <= nombres, "cada atributo esperado lleva sus ejemplos"
    assert all(len(v) == 3 for v in datos["ejemplos"].values())
    # los ejemplos no repiten expresiones del banco (si no, se mediria memoria)
    banco = {p["expresion"] for p in datos["positivas"]} | {n["expresion"] for n in datos["negativas"]}
    assert not banco & {e for v in datos["ejemplos"].values() for e in v}
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


def _res(clase, score, acierta=False, margen=0.1):
    return {"clase": clase, "score": score, "margen": margen, "acierta": acierta}


def _con(neg_max, positivas):
    return [_res("negativa", neg_max)] + [_res("positiva", p, acierta=True) for p in positivas]


def test_decidir_elige_la_representacion_con_mas_positivas_sobre_max_negativas_mas_003():
    por_rep = {
        "a": _con(0.45, [0.50] * 10),                  # corte 0.48: 10 sobre el corte
        "b": _con(0.45, [0.60] * 12 + [0.40] * 3),     # 12
        "c": _con(0.40, [0.60] * 12 + [0.40] * 3),     # 12, mismo numero: gana la mas sencilla (b)
    }
    d = decidir(por_rep, total_positivas=15)
    assert d["representacion"] == "b"
    assert d["parar"] is False


def test_decidir_fija_umbrales_con_la_regla_del_arquitecto():
    por_rep = {"a": _con(0.4312, [0.9] * 15)}
    d = decidir(por_rep, total_positivas=15)
    # max(neg)+0.03 = 0.4612 -> redondeado hacia arriba a 0.01 = 0.47; sustituir = +0.10
    assert d["umbrales"]["reutilizar"] == {"puntuacion": 0.47, "margen": 0.03}
    assert d["umbrales"]["sustituir"] == {"puntuacion": 0.57, "margen": 0.05}


def test_decidir_para_si_ninguna_llega_a_8_de_15():
    por_rep = {"a": _con(0.5, [0.9] * 7 + [0.1] * 8), "b": _con(0.5, [0.52] * 7 + [0.1] * 8)}
    d = decidir(por_rep, total_positivas=15)
    assert d["parar"] is True


def test_decidir_exacto_en_el_corte_no_cuenta_como_por_encima():
    # corte = 0.50 + 0.03 = 0.53; una positiva justo en 0.53 no esta «por encima» del corte
    por_rep = {"a": _con(0.50, [0.53] * 15)}
    d = decidir(por_rep, total_positivas=15)
    assert d["positivas_sobre_corte"]["a"] == 0
