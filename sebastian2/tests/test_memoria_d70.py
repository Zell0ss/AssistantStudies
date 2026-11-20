"""Fase 4, H1e (D70): el valor tiene que encajar con el tipo del atributo, también por alias (R13), y R12 no afecta a `retirar`.
Extractor y búsqueda semántica falsos, contra sebastian_test. Datos inventados."""
import pytest

from core.memoria.resolucion import valor_encaja
from tests.test_memoria_d69 import ID, USUARIO, _dato, _semantica_que_devuelve, _tipos, _valores  # noqa: F401
from tests.test_memoria_servicio import USER, entorno  # noqa: F401  (`entorno` es una fixture)


def _decisiones(entorno, tipo):
    return [d for d in entorno.repo.decisiones(USER) if d["tipo"] == tipo]


def _con_id_vigente(entorno):
    entorno.servicio([_dato(ID, "700111222", "numero")])[0].guardar(USER, "Mi id es 700111222")


def test_h1e_1_el_caso_de_produccion_por_alias_un_texto_en_un_atributo_numero_va_a_nota(entorno):
    _con_id_vigente(entorno)
    servicio, _ = entorno.servicio([_dato(ID, "@usuario_prueba", "texto")])             # el extractor usa el nombre exacto: alias
    salida = servicio.guardar(USER, "Mi usuario de Telegram es @usuario_prueba")

    assert "sustituir" not in _tipos(entorno)
    assert salida["data"]["notas"] == ["Mi usuario de Telegram es @usuario_prueba"] and salida["data"]["guardados"] == []
    assert _valores(entorno, ID) == ["700111222"]                                          # el id sigue vigente
    (nota,) = _decisiones(entorno, "nota")
    assert nota["senales"]["tipo_no_encaja"] is True and nota["senales"]["fuerte"] is False
    assert "@usuario_prueba" not in str(nota)                                              # la señal no lleva el valor (D42)
    assert all("tipo_no_encaja" not in d["senales"] for d in entorno.repo.decisiones(USER) if d["tipo"] != "nota")


def test_h1e_2_una_correccion_legitima_por_alias_sigue_sustituyendo(entorno):
    _con_id_vigente(entorno)
    salida = entorno.servicio([_dato(ID, "700999888", "numero", operacion="corregir")])[0].guardar(USER, "Corrige: mi id es 700999888")
    assert [g["operacion"] for g in salida["data"]["guardados"]] == ["corregir"]
    assert _valores(entorno, ID) == ["700999888"]
    assert all("tipo_no_encaja" not in d["senales"] for d in entorno.repo.decisiones(USER))


@pytest.mark.parametrize("valor,tipo,esperado", [
    ("2,4 bar", "numero", True), ("-3.5", "numero", True), ("815566372", "numero", True), ("+7", "numero", True),
    ("@usuario", "numero", False), ("unos 30", "numero", False), ("", "numero", True),
    ("--03-12", "fecha", True), ("2026-11-20", "fecha", True), ("12 de marzo", "fecha", False), ("2026-11", "fecha", False),
    ("sí", "booleano", True), ("Si", "booleano", True), ("NO", "booleano", True), ("false", "booleano", True),
    ("Verdadero", "booleano", True), ("quizá", "booleano", False),
    ("cualquier cosa", "texto", True), ("@usuario", "texto", True), ("123", "texto", True), ("x", "tipo_raro", True),
])
def test_h1e_3_valor_encaja(valor, tipo, esperado):
    assert valor_encaja(valor, tipo) is esperado


def test_h1e_4_sin_valor_vigente_y_sin_encaje_el_hecho_se_añade_como_hoy(entorno):
    _con_id_vigente(entorno)
    entorno.servicio([_dato(ID, "", "texto", operacion="retirar")])[0].guardar(USER, "Olvida mi id")        # por alias y con valor vacío
    assert _valores(entorno, ID) == []                                                                       # (5: retirar sigue funcionando)

    salida = entorno.servicio([_dato(ID, "@usuario_prueba", "texto")])[0].guardar(USER, "Mi usuario es @usuario_prueba")
    assert [g["operacion"] for g in salida["data"]["guardados"]] == ["afirmar"] and salida["data"]["notas"] == []
    assert _valores(entorno, ID) == ["@usuario_prueba"]                                                      # débil, pero no pisa nada
    assert [d["senales"].get("tipo_no_encaja") for d in _decisiones(entorno, "anadir")][-1] is True


def test_h1e_5_retirar_por_semantica_ya_no_se_debilita_por_el_tipo_valor_por_defecto(entorno):
    _con_id_vigente(entorno)
    servicio, _ = entorno.servicio([_dato(f"otro_nombre_svc_test", "", "texto", operacion="retirar")])    # texto por defecto, atributo numero
    _semantica_que_devuelve(servicio, ID)
    salida = servicio.guardar(USER, "Olvida mi id")
    assert [g["operacion"] for g in salida["data"]["guardados"]] == ["retirar"] and _valores(entorno, ID) == []
    (reutilizar,) = _decisiones(entorno, "reutilizar_atributo")[-1:]
    assert reutilizar["senales"]["fuerte"] is True and reutilizar["senales"]["via"] == "semantica"


def test_h1e_lo_recien_creado_no_se_juzga_por_tipo_aunque_el_valor_parezca_raro(entorno):
    """El atributo nuevo toma el tipo del propio hecho: no hay nada contra lo que comparar."""
    salida = entorno.servicio([_dato(ID, "@usuario_prueba", "numero")])[0].guardar(USER, "id raro")
    assert [g["operacion"] for g in salida["data"]["guardados"]] == ["afirmar"]
    assert all("tipo_no_encaja" not in d["senales"] for d in entorno.repo.decisiones(USER))
