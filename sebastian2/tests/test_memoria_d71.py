"""Fase 4, H1f (D71): `search_memory` no contesta «nada» cuando sabe de quién se pregunta. R14 (entidad sí, atributo no), R15 (notas por
palabra) y R16 (log sin contenido). Embedder falso, Qdrant en memoria y `sebastian_test`; datos inventados."""
from unittest.mock import patch

from tests.test_memoria_consulta import BASE, OTRO, USER, _con_nota, entorno  # noqa: F401  (`entorno` es una fixture)

NOTA = "Mi usuario de Telegram es @usuario_prueba"


def _con_id(entorno, valor="700111222"):
    aid = entorno.repo.crear_atributo(f"telegram_id_{BASE}", "Identificador de Telegram", tipo_valor="numero")
    yo = entorno.repo.entidad_usuario(USER)
    return entorno.repo.anadir_hecho(USER, yo, aid, valor)


def _con_nota_solo_en_sql(entorno, user, texto):
    """Una nota sin punto en Qdrant: la semántica no la ve, solo la palabra."""
    yo = entorno.repo.entidad_usuario(user)
    return entorno.repo.anadir_hecho(user, yo, entorno.repo.atributos_por_alias("nota")[0]["id"], texto)


def _consultar(entorno, **kw):
    with patch("core.memoria.servicio.logger") as log:
        salida = entorno.servicio().consultar(USER, **kw)
    linea = next(c.args[0] for c in log.info.call_args_list if c.args[0].startswith("memoria.consultar:"))
    return salida, linea, [str(c) for c in log.mock_calls]


def test_h1f_1_el_caso_de_produccion_sale_el_hecho_y_la_nota_por_palabra_y_el_log_lo_dice(entorno):
    _con_id(entorno)
    _con_nota(entorno, USER, NOTA)                                      # con su punto en Qdrant: aun asi no llega al umbral
    salida, linea, _ = _consultar(entorno, query="datos de Telegram", entidad="yo", atributo="telegram")

    # los hechos vigentes de la entidad: el id y, como en toda consulta solo por entidad, la propia nota (atributo `nota`)
    assert [(h["atributo"], h["valor"]) for h in salida["hechos"]] == [(f"telegram_id_{BASE}", "700111222"), ("nota", NOTA)]
    assert salida["atributo_no_resuelto"] is True and salida["historial"] == []
    assert [n["texto"] for n in salida["notas"]] == [NOTA]
    assert "entidad=resuelta atributo=no_resuelta notas_sem=0 notas_palabra=1" in linea


def test_h1f_1b_la_nota_semantica_va_primero_y_no_se_repite_por_palabra(entorno):
    _con_nota(entorno, USER, "Telegram: el usuario va con arroba")      # misma palabra y muy parecida a la consulta
    _con_nota_solo_en_sql(entorno, USER, "Otra nota sobre Telegram")
    salida, linea, _ = _consultar(entorno, query="Telegram el usuario va con arroba", entidad="yo", atributo="telegram")
    assert [n["texto"] for n in salida["notas"]] == ["Telegram: el usuario va con arroba", "Otra nota sobre Telegram"]
    assert "notas_sem=1 notas_palabra=1" in linea


def test_h1f_2_una_entidad_que_no_se_resuelve_sigue_dando_cero_hechos(entorno):
    _con_id(entorno)
    for kw in ({"entidad": "Nadie"}, {"entidad": "Nadie", "atributo": "telegram_id_" + BASE}, {"entidad": "Nadie", "atributo": "telegram"}):
        salida, linea, _ = _consultar(entorno, query="x", **kw)
        assert salida["hechos"] == [] and "atributo_no_resuelto" not in salida
        assert "entidad=no_resuelta" in linea


def test_h1f_3_sin_entidad_ni_atributo_cero_hechos_y_solo_notas_semanticas(entorno):
    _con_id(entorno)
    _con_nota(entorno, USER, "Uso camisetas UV para bañarme en verano")
    salida, linea, _ = _consultar(entorno, query="camisetas UV para bañarme")
    assert salida["hechos"] == [] and "atributo_no_resuelto" not in salida
    assert [n["texto"] for n in salida["notas"]] == ["Uso camisetas UV para bañarme en verano"]
    assert "entidad=no_pedida atributo=no_pedida notas_sem=1 notas_palabra=0" in linea
    # sin entidad y con un atributo que no se resuelve tampoco se amplia a «todo»
    salida, _, _ = _consultar(entorno, query="x", atributo="telegram")
    assert salida["hechos"] == [] and "atributo_no_resuelto" not in salida


def test_h1f_3b_las_notas_por_palabra_salen_aunque_no_haya_query(entorno):
    _con_nota_solo_en_sql(entorno, USER, NOTA)
    salida, linea, _ = _consultar(entorno, query="", entidad="yo", atributo="telegram")
    assert [n["texto"] for n in salida["notas"]] == [NOTA] and "notas_sem=0 notas_palabra=1" in linea


def test_h1f_4_las_notas_de_otro_usuario_nunca_salen_por_palabra(entorno):
    _con_nota_solo_en_sql(entorno, OTRO, NOTA)
    salida, linea, _ = _consultar(entorno, query="datos de Telegram", entidad="yo", atributo="telegram")
    assert salida["notas"] == [] and "notas_palabra=0" in linea


def test_h1f_5_las_notas_cerradas_no_salen_por_palabra(entorno):
    hid = _con_nota_solo_en_sql(entorno, USER, NOTA)
    entorno.repo.retirar_hecho(hid)
    salida, _, _ = _consultar(entorno, query="datos de Telegram", entidad="yo", atributo="telegram")
    assert salida["notas"] == []


def test_h1f_6_los_terminos_cortos_y_yo_no_buscan_nada(entorno):
    _con_nota_solo_en_sql(entorno, USER, "Yo de eso no sé nada, y el sol sí")
    for entidad, atributo in (("yo", None), ("yo", "de"), ("yo", "sol"), ("el", "y")):
        salida, linea, _ = _consultar(entorno, query="", entidad=entidad, atributo=atributo)
        assert salida["notas"] == [] and "notas_palabra=0" in linea, (entidad, atributo)


def test_h1f_6b_la_palabra_es_completa_y_se_normaliza(entorno):
    _con_nota_solo_en_sql(entorno, USER, "Mi canción favorita es esa")
    _con_nota_solo_en_sql(entorno, USER, "Telegramero de pro")                   # «telegram» no es una palabra de esta nota
    salida, _, _ = _consultar(entorno, query="", atributo="Cancion")             # sin tilde en la petición, con tilde en la nota
    assert [n["texto"] for n in salida["notas"]] == ["Mi canción favorita es esa"]
    salida, _, _ = _consultar(entorno, query="", atributo="telegram")
    assert salida["notas"] == []


def test_h1f_6c_el_tope_de_notas_sigue_siendo_tres_y_la_mas_reciente_va_primero(entorno):
    for n in range(5):
        _con_nota_solo_en_sql(entorno, USER, f"Telegram nota {n}")
    salida, linea, _ = _consultar(entorno, query="", atributo="telegram")
    assert [n["texto"] for n in salida["notas"]] == ["Telegram nota 4", "Telegram nota 3", "Telegram nota 2"]
    assert "notas_palabra=3" in linea


def test_h1f_7_una_marca_en_la_entidad_el_atributo_y_la_query_no_sale_en_ningun_log(entorno):
    _con_nota_solo_en_sql(entorno, USER, "ZZCONS en una nota")
    for kw in ({"entidad": "ZZCONS", "atributo": "ZZCONS"}, {"entidad": "yo", "atributo": "ZZCONS"}, {"atributo": "ZZCONS"}):
        salida, linea, llamadas = _consultar(entorno, query="ZZCONS", **kw)
        assert llamadas and not any("ZZCONS" in x for x in llamadas), kw
        assert "ZZCONS" not in linea


def test_h1f_el_prompt_de_alfred_sabe_que_hacer_con_atributo_no_resuelto():
    from core.orchestrator import _ALFRED_SYSTEM
    assert "atributo_no_resuelto" in _ALFRED_SYSTEM and "que vienen a cuento" in _ALFRED_SYSTEM
    assert "si ninguno viene a cuento, dilo" in _ALFRED_SYSTEM and "D71" in _ALFRED_SYSTEM


def test_h1f_8_con_atributo_resuelto_todo_sigue_como_hoy(entorno):
    _con_id(entorno)
    salida, linea, _ = _consultar(entorno, query="mi id", entidad="yo", atributo=f"telegram_id_{BASE}")
    assert [h["valor"] for h in salida["hechos"]] == ["700111222"] and "atributo_no_resuelto" not in salida
    assert "entidad=resuelta atributo=resuelta" in linea
