"""H2 (fase 2, plan §3 H2.2): reglas de resolucion y de decision del hecho. Funciones puras: sin BD ni API."""
from core.memoria.ajustes import umbrales
from core.memoria.resolucion import (
    compatible, decidir_hecho, resolver_atributo, resolver_entidad,
)

U = umbrales({})   # reutilizar 0.58 / 0.03, sustituir 0.68 / 0.05 (calibrados en H1)


def _vigente(ident, valor):
    return {"id": ident, "valor": valor}


# --- decidir_hecho: reglas del plan ---------------------------------------------------------

def test_varios_anade():
    d = decidir_hecho("afirmar", "varios", [_vigente(1, "frutos secos")], "marisco", fuerte=False)
    assert d.tipo == "anadir"


def test_varios_mismo_valor_sin_cambio():
    d = decidir_hecho("afirmar", "varios", [_vigente(1, "Frutos Secos")], "frutos secos", fuerte=True)
    assert d.tipo == "sin_cambio"


def test_uno_sin_vigente_anade():
    assert decidir_hecho("afirmar", "uno", [], "Oviedo", fuerte=False).tipo == "anadir"


def test_uno_igual_sin_cambio():
    assert decidir_hecho("afirmar", "uno", [_vigente(7, "Oviedo")], "oviedo", fuerte=True).tipo == "sin_cambio"


def test_uno_distinto_fuerte_sustituye():
    d = decidir_hecho("corregir", "uno", [_vigente(7, "Gijón")], "Oviedo", fuerte=True)
    assert d.tipo == "sustituir" and d.hecho_id == 7


def test_uno_distinto_debil_va_a_nota():
    d = decidir_hecho("corregir", "uno", [_vigente(7, "Gijón")], "Oviedo", fuerte=False)
    assert d.tipo == "nota" and d.hecho_id is None


def test_retirar_fuerte_cierra():
    d = decidir_hecho("retirar", "uno", [_vigente(7, "camisetas UV")], "", fuerte=True)
    assert d.tipo == "retirar" and d.hecho_id == 7


def test_retirar_debil_no_toca():
    d = decidir_hecho("retirar", "uno", [_vigente(7, "camisetas UV")], "", fuerte=False)
    assert d.tipo == "sin_cambio" and "no he encontrado" in d.aviso.lower()


def test_retirar_sin_vigente_no_toca_y_avisa():
    d = decidir_hecho("retirar", "uno", [], "", fuerte=True)
    assert d.tipo == "sin_cambio" and d.aviso


def test_retirar_de_varios_cierra_el_que_coincide():
    vigentes = [_vigente(1, "frutos secos"), _vigente(2, "marisco")]
    d = decidir_hecho("retirar", "varios", vigentes, "Marisco", fuerte=True)
    assert d.tipo == "retirar" and d.hecho_id == 2


def test_retirar_de_varios_sin_coincidencia_ambigua_no_toca():
    vigentes = [_vigente(1, "frutos secos"), _vigente(2, "marisco")]
    d = decidir_hecho("retirar", "varios", vigentes, "", fuerte=True)
    assert d.tipo == "sin_cambio" and d.aviso


# --- compatibilidad de tipo -----------------------------------------------------------------

def test_tipo_incompatible_es_debil():
    assert compatible("persona", "persona") and compatible("*", "vehiculo")
    assert compatible("persona,mascota", "mascota")
    assert not compatible("proyecto", "persona")
    attr = {"id": 3, "nombre": "estado", "tipos_entidad": "proyecto"}
    r = resolver_atributo([attr], [], U, tipo_entidad="persona")
    assert r.accion == "reutilizar" and r.fuerte is False   # alias exacto, pero el tipo no encaja


# --- escalera de resolucion (D35) -----------------------------------------------------------

def test_alias_exacto_es_fuerte():
    attr = {"id": 3, "nombre": "alergia", "tipos_entidad": "persona"}
    r = resolver_atributo([attr], [], U, tipo_entidad="persona")
    assert (r.accion, r.id, r.fuerte, r.via) == ("reutilizar", 3, True, "alias")


def test_semantica_fuerte_con_puntuacion_y_margen_altos():
    cands = [{"id": 5, "score": 0.72, "tipos_entidad": "*"}, {"id": 6, "score": 0.60}]
    r = resolver_atributo([], cands, U, tipo_entidad="persona")
    assert (r.accion, r.id, r.fuerte, r.via) == ("reutilizar", 5, True, "semantica")


def test_semantica_debil_entre_reutilizar_y_sustituir():
    cands = [{"id": 5, "score": 0.62, "tipos_entidad": "*"}, {"id": 6, "score": 0.55}]
    r = resolver_atributo([], cands, U, tipo_entidad="persona")
    assert (r.accion, r.id, r.fuerte) == ("reutilizar", 5, False)


def test_semantica_con_margen_pequeno_no_reutiliza():
    cands = [{"id": 5, "score": 0.70, "tipos_entidad": "*"}, {"id": 6, "score": 0.69}]
    assert resolver_atributo([], cands, U, tipo_entidad="persona").accion == "crear"


def test_por_debajo_de_reutilizar_se_crea():
    r = resolver_atributo([], [{"id": 5, "score": 0.40, "tipos_entidad": "*"}], U, tipo_entidad="persona")
    assert (r.accion, r.id, r.fuerte) == ("crear", None, False)


def test_alias_ambiguo_cae_a_la_semantica():
    a = {"id": 1, "nombre": "a", "tipos_entidad": "*"}
    b = {"id": 2, "nombre": "b", "tipos_entidad": "*"}
    assert resolver_atributo([a, b], [], U, tipo_entidad="persona").accion == "crear"


def test_entidad_alias_exacto_fuerte_y_tipo_distinto_debil():
    paco = {"id": 9, "nombre": "Paco", "tipo": "persona"}
    assert resolver_entidad([paco], [], U, tipo="persona").fuerte is True
    assert resolver_entidad([paco], [], U, tipo="vehiculo").fuerte is False
    assert resolver_entidad([paco], [], U, tipo="otro").fuerte is True   # «otro» no contradice


def test_entidad_semantica_y_nueva():
    cands = [{"id": 9, "score": 0.9, "tipo_entidad": "persona"}, {"id": 8, "score": 0.5}]
    r = resolver_entidad([], cands, U, tipo="persona")
    assert (r.accion, r.id, r.via) == ("reutilizar", 9, "semantica")
    assert resolver_entidad([], [], U, tipo="persona").accion == "crear"
