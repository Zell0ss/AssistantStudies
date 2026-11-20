"""Fase 4, H1d (D69): un dato no sustituye a otro de la misma frase. Extractor, embedder y búsqueda semántica falsos, contra
sebastian_test. Datos inventados.

R11: lo creado en esta llamada no es candidato semántico (por alias exacto sí se reutiliza).
R12: un `tipo_valor` distinto del del candidato hace débil la resolución semántica.
"""
from core.memoria.resolucion import resolver_atributo
from tests.test_memoria_servicio import SUFIJO, USER, entorno, _hecho  # noqa: F401  (`entorno` es una fixture)

ID = f"id_telegram{SUFIJO}"
USUARIO = f"usuario_telegram{SUFIJO}"
U = {"reutilizar": {"puntuacion": 0.55, "margen": 0.03}, "sustituir": {"puntuacion": 0.70, "margen": 0.05}}


def _dato(atributo, valor, tipo_valor, **kw):
    return _hecho(entidad="yo", tipo_entidad="persona", atributo=atributo, valor=valor, tipo_valor=tipo_valor,
                  cardinalidad="uno", descripcion_atributo=f"descripcion de {atributo}", **kw)


def _semantica_que_devuelve(servicio, nombre, puntuacion=0.87, margen=0.36):
    """Búsqueda semántica falsa: el atributo `nombre` (si ya existe) con `puntuacion`, y de segunda, `nota` con `puntuacion - margen`."""
    repo = servicio._repo

    def buscar(consulta, *a, **kw):
        existente = repo.atributos_por_alias(nombre)
        if not existente:
            return []
        nota = repo.atributos_por_alias("nota")[0]
        return [{"id": existente[0]["id"], "score": puntuacion}, {"id": nota["id"], "score": round(puntuacion - margen, 3)}]
    servicio._catalogo.buscar_atributos = buscar


def _tipos(entorno):
    return [d["tipo"] for d in entorno.repo.decisiones(USER)]


def _valores(entorno, nombre):
    yo = entorno.repo.entidad_usuario(USER, None)
    return [h["valor"] for h in entorno.repo.hechos_vigentes(USER, yo, entorno.repo.atributos_por_alias(nombre)[0]["id"])]


def test_h1d_1_el_caso_de_produccion_id_y_usuario_en_una_llamada_no_se_sustituyen(entorno):
    servicio, _ = entorno.servicio([_dato(ID, "700111222", "numero"), _dato(USUARIO, "@usuario_prueba", "texto")])
    _semantica_que_devuelve(servicio, ID)                     # al segundo hecho le sale el primer atributo con 0,87 y margen 0,36
    salida = servicio.guardar(USER, "Recuerda que en Telegram mi id es 700111222 y mi usuario es @usuario_prueba")

    tipos = _tipos(entorno)
    assert tipos.count("crear_atributo") == 2 and tipos.count("anadir") == 2
    assert "sustituir" not in tipos and "reutilizar_atributo" not in tipos
    assert [g["operacion"] for g in salida["data"]["guardados"]] == ["afirmar", "afirmar"]       # `anadir` se cuenta como `afirmar`
    assert _valores(entorno, ID) == ["700111222"] and _valores(entorno, USUARIO) == ["@usuario_prueba"]


def test_h1d_2_el_mismo_nombre_en_la_misma_llamada_se_reutiliza_por_alias(entorno):
    varios = {"cardinalidad": "varios"}
    servicio, _ = entorno.servicio([_dato(USUARIO, "primero", "texto") | varios, _dato(USUARIO, "segundo", "texto") | varios])
    servicio.guardar(USER, "dos valores del mismo atributo")
    tipos = _tipos(entorno)
    assert tipos.count("crear_atributo") == 1 and tipos.count("reutilizar_atributo") == 1 and tipos.count("anadir") == 2
    assert sorted(_valores(entorno, USUARIO)) == ["primero", "segundo"]
    (reutilizada,) = [d for d in entorno.repo.decisiones(USER) if d["tipo"] == "reutilizar_atributo"]
    assert "via=alias" in reutilizada["detalle"]


def test_h1d_3_un_tipo_valor_distinto_por_semantica_fuerte_va_a_nota_y_el_valor_anterior_sigue_vigente(entorno):
    entorno.servicio([_dato(ID, "700111222", "numero")])[0].guardar(USER, "Mi id es 700111222")      # turno anterior
    servicio, _ = entorno.servicio([_dato(USUARIO, "@usuario_prueba", "texto")])
    _semantica_que_devuelve(servicio, ID)
    salida = servicio.guardar(USER, "Mi usuario es @usuario_prueba")

    assert "sustituir" not in _tipos(entorno) and "nota" in _tipos(entorno)
    assert salida["data"]["notas"] == ["Mi usuario es @usuario_prueba"] and salida["data"]["guardados"] == []
    assert _valores(entorno, ID) == ["700111222"]                                                       # no se perdió
    (reutilizar,) = [d for d in entorno.repo.decisiones(USER) if d["tipo"] == "reutilizar_atributo"]
    assert reutilizar["senales"]["fuerte"] is False and reutilizar["senales"]["via"] == "semantica"


def test_h1d_4_control_el_mismo_tipo_valor_por_semantica_fuerte_sigue_sustituyendo(entorno):
    entorno.servicio([_dato(ID, "700111222", "numero")])[0].guardar(USER, "Mi id es 700111222")
    servicio, _ = entorno.servicio([_dato(f"otro_nombre{SUFIJO}", "700333444", "numero")])
    _semantica_que_devuelve(servicio, ID)
    salida = servicio.guardar(USER, "Mi id ahora es 700333444")

    assert [g["operacion"] for g in salida["data"]["guardados"]] == ["corregir"]                 # `sustituir` se cuenta como `corregir`
    assert "sustituir" in _tipos(entorno) and _valores(entorno, ID) == ["700333444"]
    (reutilizar,) = [d for d in entorno.repo.decisiones(USER) if d["tipo"] == "reutilizar_atributo"]
    assert reutilizar["senales"]["fuerte"] is True


def test_h1d_r11_lo_creado_en_el_turno_no_cuenta_aunque_el_tipo_valor_coincida(entorno):
    """R11 sola, sin que R12 intervenga: dos datos numero en una llamada, el segundo no sustituye al primero."""
    servicio, _ = entorno.servicio([_dato(ID, "700111222", "numero"), _dato(f"otro_id{SUFIJO}", "700333444", "numero")])
    _semantica_que_devuelve(servicio, ID)
    servicio.guardar(USER, "Mi id es 700111222 y el otro 700333444")
    assert "sustituir" not in _tipos(entorno) and _tipos(entorno).count("crear_atributo") == 2
    assert _valores(entorno, ID) == ["700111222"] and _valores(entorno, f"otro_id{SUFIJO}") == ["700333444"]


def test_h1d_r12_el_tipo_valor_solo_pesa_por_semantica_no_por_alias():
    candidato = {"id": 7, "score": 0.9, "tipos_entidad": "*", "tipo_valor": "numero"}
    por_semantica = resolver_atributo([], [candidato, {**candidato, "id": 8, "score": 0.5}], U, tipo_entidad="persona", tipo_valor="texto")
    assert por_semantica.via == "semantica" and por_semantica.fuerte is False
    mismo = resolver_atributo([], [candidato, {**candidato, "id": 8, "score": 0.5}], U, tipo_entidad="persona", tipo_valor="numero")
    assert mismo.fuerte is True
    sin_dato = resolver_atributo([], [candidato, {**candidato, "id": 8, "score": 0.5}], U, tipo_entidad="persona")
    assert sin_dato.fuerte is True                                                                       # sin `tipo_valor`, como antes
    por_alias = resolver_atributo([{"id": 7, "tipos_entidad": "*", "tipo_valor": "numero"}], [], U, tipo_entidad="persona", tipo_valor="texto")
    assert por_alias.via == "alias" and por_alias.fuerte is True
