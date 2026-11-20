"""Fase 4, H1 (D65; plan §2.4 y §3, pruebas 5-10): filtro simple, firma y novedad. Funciones puras, sin BD ni red."""
from datetime import timedelta
from decimal import Decimal

from modules.vigilancias.filtro import es_nuevo, firma, normalizar, pasa_filtro, seleccionar
from tests.fakes_vigilancias import AHORA, hacer_anuncio


def test_normalizar_minusculas_sin_acentos_y_capacidades_pegadas():
    assert normalizar("Mac MINI Ñandú 8 GB, SSD 1 Tb (garantía)") == ["mac", "mini", "nandu", "8gb", "ssd", "1tb", "garantia"]
    assert normalizar("") == normalizar(None) == []


def test_5_excluir_casa_por_palabras_enteras():
    filtros = {"precio_min": None, "precio_max": None, "excluir": ["8gb", "intel"]}
    assert pasa_filtro(hacer_anuncio(titulo="Mac mini M4 128 GB SSD", descripcion=""), filtros)        # «128gb» no es «8gb»
    assert not pasa_filtro(hacer_anuncio(titulo="Mac mini 8 GB RAM", descripcion=""), filtros)
    assert not pasa_filtro(hacer_anuncio(titulo="Mac mini Intel i7 2018", descripcion=""), filtros)


def test_5b_excluir_mira_tambien_la_descripcion_y_acepta_secuencias_y_i7x():
    filtros = {"excluir": ["i7", "para piezas"]}
    assert not pasa_filtro(hacer_anuncio(titulo="Mac mini", descripcion="Funciona, pero Para  PIEZAS."), filtros)
    assert pasa_filtro(hacer_anuncio(titulo="Mac mini i7x", descripcion="para casi todo, piezas nuevas"), filtros)   # ni «i7x» ni la secuencia partida
    assert not pasa_filtro(hacer_anuncio(titulo="Mac mini i7", descripcion=""), filtros)


def test_6_precio_minimo_maximo_y_sin_precio():
    filtros = {"precio_min": 300, "precio_max": None, "excluir": []}
    assert not pasa_filtro(hacer_anuncio(precio="40"), filtros)
    assert not pasa_filtro(hacer_anuncio(precio=None), filtros)
    assert pasa_filtro(hacer_anuncio(precio="5000"), filtros)                                          # precio_max nulo: no limita
    assert pasa_filtro(hacer_anuncio(precio="300"), filtros)                                           # el extremo entra
    assert not pasa_filtro(hacer_anuncio(precio="1500.01"), {"precio_min": None, "precio_max": 1500})


def test_7_un_anuncio_reservado_no_pasa():
    assert not pasa_filtro(hacer_anuncio(reservado=True), {"precio_min": None, "precio_max": None, "excluir": []})


def test_8_el_mismo_id_de_dos_consultas_sale_una_vez_y_dos_ids_con_la_misma_firma_tambien():
    a = hacer_anuncio(id="x1", titulo="Mac mini M4", descripcion="Nuevo")
    mismo_id = hacer_anuncio(id="x1", titulo="Mac mini M4", descripcion="Nuevo")
    misma_firma = hacer_anuncio(id="x2", titulo="MAC MINI  m4", descripcion="nuevo!")
    otro = hacer_anuncio(id="x3", titulo="Mac mini M2", descripcion="Otro")
    s = seleccionar([a, mismo_id, misma_firma, otro], {}, {"excluir": []}, AHORA)
    assert [x.id for x in s.candidatos] == ["x1", "x3"]               # el primero que llega se queda; el de la misma firma no es candidato
    assert sorted(x.id for x in s.nuevos) == ["x1", "x2", "x3"]       # el de la misma firma sigue siendo «nuevo»: se guardará como visto


def _visto(a, **cambios):
    return {"precio": a.precio, "firma": firma(a), "modificado": a.modificado, **cambios}


def test_9_visto_igual_no_es_nuevo_otro_precio_o_otro_texto_si():
    a = hacer_anuncio(modificado=AHORA - timedelta(hours=1))
    assert not es_nuevo(a, _visto(a), AHORA)
    assert es_nuevo(a, _visto(a, precio=Decimal("950.00")), AHORA)                                      # otro precio
    assert es_nuevo(hacer_anuncio(modificado=a.modificado, descripcion="Descripción cambiada"), _visto(a), AHORA)
    assert not es_nuevo(a, _visto(a, precio=Decimal("900.00")), AHORA)                                 # DECIMAL(10,2) de la BD = 900


def test_9b_subir_el_anuncio_sin_cambios_no_vuelve_a_salir():
    visto = hacer_anuncio(modificado=AHORA - timedelta(hours=30))
    subido = hacer_anuncio(modificado=AHORA - timedelta(hours=1))                                      # bump: misma firma y precio
    assert not es_nuevo(subido, _visto(visto), AHORA)


def test_10_la_ventana_de_novedad_es_de_48_horas():
    assert not es_nuevo(hacer_anuncio(modificado=AHORA - timedelta(hours=49)), None, AHORA)
    assert es_nuevo(hacer_anuncio(modificado=AHORA - timedelta(hours=47)), None, AHORA)


def test_orden_duplicados_novedad_filtro_y_candidatos_del_mas_reciente_al_mas_antiguo():
    viejo = hacer_anuncio(id="v", titulo="Mac mini M2", modificado=AHORA - timedelta(hours=40))
    reciente = hacer_anuncio(id="r", titulo="Mac mini M4", modificado=AHORA - timedelta(hours=2))
    caro = hacer_anuncio(id="c", titulo="Mac mini M4 Pro", precio="9000", modificado=AHORA - timedelta(hours=1))
    fuera = hacer_anuncio(id="f", titulo="Mac mini M1", modificado=AHORA - timedelta(hours=60))
    s = seleccionar([viejo, reciente, caro, fuera], {}, {"precio_max": 2000, "excluir": []}, AHORA)
    assert [x.id for x in s.candidatos] == ["r", "v"]
    assert sorted(x.id for x in s.nuevos) == ["c", "r", "v"]          # «caro» es nuevo aunque el filtro lo descarte; «fuera» no es nuevo
