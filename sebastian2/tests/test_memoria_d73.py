"""Fase 4, H1i (D73): una consulta solo con `query` busca por sus palabras en entidades, atributos y notas (R23, R24).
Embedder falso, Qdrant en memoria y `sebastian_test`; datos inventados."""
from tests.test_memoria_consulta import BASE, OTRO, USER, _con_nota, entorno  # noqa: F401  (`entorno` es una fixture)
from tests.test_memoria_d71 import NOTA, _con_id, _con_nota_solo_en_sql, _consultar

ATRIBUTO_ID = f"telegram_id_{BASE}"


def _hechos(salida):
    return [(h["entidad"], h["atributo"], h["valor"]) for h in salida["hechos"]]


def test_h1i_1_el_caso_de_la_traza_solo_query_telegram_saca_el_hecho_y_la_nota(entorno):
    _con_id(entorno)
    _con_nota(entorno, USER, NOTA)                                       # con su punto en Qdrant: no llega al umbral semántico
    salida, linea, _ = _consultar(entorno, query="Telegram")

    assert _hechos(salida) == [("yo", ATRIBUTO_ID, "700111222")]         # la nota no sale como hecho: va por R15/R24
    assert salida["por_palabras"] is True and salida["historial"] == []
    assert [n["texto"] for n in salida["notas"]] == [NOTA]
    assert "por_palabras=1" in linea and "notas_sem=0 notas_palabra=1" in linea
    assert "entidad=no_pedida atributo=no_pedida" in linea


def test_h1i_2_una_pregunta_larga_da_el_mismo_resultado(entorno):
    _con_id(entorno)
    _con_nota(entorno, USER, NOTA)
    salida, linea, _ = _consultar(entorno, query="¿qué datos tienes de mí en Telegram?")
    assert _hechos(salida) == [("yo", ATRIBUTO_ID, "700111222")] and salida["por_palabras"] is True
    assert [n["texto"] for n in salida["notas"]] == [NOTA] and "por_palabras=1" in linea


def test_h1i_3_coincidencia_por_entidad(entorno):
    entorno.hecho(USER, "Paco", "persona", "alergia", "frutos secos")
    entorno.hecho(USER, "Paco", "persona", "parentesco", "cuñado")
    entorno.hecho(USER, "Marisol", "persona", "alergia", "polen")
    salida, linea, _ = _consultar(entorno, query="Paco")
    assert _hechos(salida) == [("Paco", "parentesco", "cuñado"), ("Paco", "alergia", "frutos secos")]      # los más recientes primero
    assert salida["por_palabras"] is True and "por_palabras=2" in linea


def test_h1i_3b_coincidencia_por_una_pieza_del_nombre_del_atributo_y_por_alias_de_la_entidad(entorno):
    entorno.hecho(USER, "Paco", "persona", "alergia", "frutos secos")
    entorno.repo.anadir_alias_entidad(entorno.repo.entidades_por_alias(USER, "Paco")[0]["id"], "Pacorro")
    por_atributo, _, _ = _consultar(entorno, query="alergia")
    por_alias, _, _ = _consultar(entorno, query="¿qué sabes de Pacorro?")
    assert _hechos(por_atributo) == _hechos(por_alias) == [("Paco", "alergia", "frutos secos")]


def test_h1i_4_los_hechos_de_otro_usuario_nunca_salen(entorno):
    entorno.hecho(OTRO, "Paco", "persona", "alergia", "marisco")
    salida, linea, _ = _consultar(entorno, query="Paco")
    assert salida["hechos"] == [] and "por_palabras" not in salida and "por_palabras=0" in linea


def test_h1i_5_los_hechos_cerrados_nunca_salen(entorno):
    hid = entorno.hecho(USER, "Paco", "persona", "alergia", "frutos secos")
    entorno.repo.retirar_hecho(hid)
    salida, _, _ = _consultar(entorno, query="Paco", historial=True)
    assert salida["hechos"] == [] and salida["historial"] == [] and "por_palabras" not in salida


def test_h1i_6_con_entidad_o_atributo_todo_sigue_como_en_d71(entorno):
    _con_id(entorno)
    _con_nota_solo_en_sql(entorno, USER, NOTA)
    # entidad que no se resuelve: 0 hechos, aunque la query tenga una palabra que coincidiría
    salida, linea, _ = _consultar(entorno, query="Telegram", entidad="Nadie")
    assert salida["hechos"] == [] and "por_palabras" not in salida and "por_palabras=0" in linea
    # entidad sí, atributo no: los hechos vigentes de la entidad (R14), no «por palabras»
    salida, _, _ = _consultar(entorno, query="Telegram", entidad="yo", atributo="telegram")
    assert salida["atributo_no_resuelto"] is True and "por_palabras" not in salida
    # atributo sin entidad que no se resuelve: 0 hechos
    salida, _, _ = _consultar(entorno, query="Telegram", atributo="telegram")
    assert salida["hechos"] == [] and "por_palabras" not in salida
    # ambos resueltos: lo de siempre
    salida, _, _ = _consultar(entorno, query="Telegram", entidad="yo", atributo=ATRIBUTO_ID)
    assert _hechos(salida) == [("yo", ATRIBUTO_ID, "700111222")] and "por_palabras" not in salida


def test_h1i_7_los_terminos_cortos_y_yo_no_buscan_nada(entorno):
    _con_id(entorno)
    for query in ("de mi", "yo", "mi yo de", "¿y a mí?"):
        salida, linea, _ = _consultar(entorno, query=query)
        assert salida["hechos"] == [] and "por_palabras" not in salida and "por_palabras=0" in linea, query


def test_h1i_8_una_marca_en_la_query_no_sale_en_ningun_log(entorno):
    entorno.hecho(USER, "ZZQUERY", "persona", "alergia", "polen")
    _con_nota_solo_en_sql(entorno, USER, "Una nota de ZZQUERY")
    salida, linea, llamadas = _consultar(entorno, query="¿qué sabes de ZZQUERY?")
    assert [h["valor"] for h in salida["hechos"]] == ["polen"] and [n["texto"] for n in salida["notas"]] == ["Una nota de ZZQUERY"]
    assert llamadas and not any("ZZQUERY" in x for x in llamadas) and "ZZQUERY" not in linea


def test_h1i_9_como_mucho_20_hechos_los_mas_recientes_primero(entorno):
    for n in range(25):
        entorno.hecho(USER, "Paco", "persona", "alergia", f"alergia {n:02d}")
    salida, linea, _ = _consultar(entorno, query="Paco")
    assert len(salida["hechos"]) == 20 and salida["hechos"][0]["valor"] == "alergia 24" and salida["hechos"][-1]["valor"] == "alergia 05"
    assert "por_palabras=20" in linea


def test_h1i_r24_las_palabras_de_la_query_buscan_notas_tambien_con_entidad(entorno):
    _con_nota_solo_en_sql(entorno, USER, NOTA)
    salida, linea, _ = _consultar(entorno, query="Telegram", entidad="yo")                # `yo` no aporta términos; la query sí
    assert [n["texto"] for n in salida["notas"]] == [NOTA] and "notas_palabra=1" in linea
    # y se unen a las de la entidad y el atributo, sin repetir
    _con_nota_solo_en_sql(entorno, USER, "Otra nota con cumpleaños y Telegram")
    salida, _, _ = _consultar(entorno, query="Telegram", entidad="yo", atributo="telegram")
    assert len(salida["notas"]) == 2 and len({n["texto"] for n in salida["notas"]}) == 2


def test_h1i_el_log_conserva_el_orden_anterior_y_añade_por_palabras_al_final(entorno):
    _, linea, _ = _consultar(entorno, query="nada que ver")
    assert linea.endswith("notas_sem=0 notas_palabra=0 por_palabras=0")


def test_h1i_el_prompt_de_alfred_sabe_que_hacer_con_por_palabras():
    from core.orchestrator import _ALFRED_SYSTEM
    assert "`por_palabras`" in _ALFRED_SYSTEM and "coincidencia de palabras con la pregunta" in _ALFRED_SYSTEM
    assert "D73" in _ALFRED_SYSTEM
