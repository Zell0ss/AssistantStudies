"""H3 (R7, D41 y D42): la frase de origen de cada hecho y la purga al olvidar. Sin API: extractor y embedder
falsos, Qdrant en memoria y `sebastian_test` (D25)."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.memoria.ajustes import umbrales
from core.memoria.catalogo import Catalogo
from core.memoria.repositorio import RepositorioMemoria
from core.memoria.servicio import ServicioMemoria
from db.connection import close_connection, get_connection
from scripts.memoria.crear_colecciones import crear_colecciones
from tests.fakes_memoria import EmbedderFalso, qdrant_en_memoria

USER = "test_mem_fuentes_a"
OTRO = "test_mem_fuentes_b"
BASE = "fte_test"
SUFIJO = "_fte_test"


def _limpiar(conn):
    cur = conn.cursor()
    u = (USER, OTRO)
    cur.execute("DELETE FROM mem_decisiones WHERE user_id IN (%s, %s)", u)
    cur.execute("UPDATE mem_hechos SET superseded_by = NULL WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_hechos WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_fuentes WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_entidad_alias WHERE entidad_id IN"
                " (SELECT id FROM mem_entidades WHERE user_id IN (%s, %s))", u)
    cur.execute("DELETE FROM mem_entidades WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_atributo_alias WHERE atributo_id IN"
                " (SELECT id FROM mem_atributos WHERE nombre LIKE %s)", (f"%{SUFIJO}",))
    cur.execute("DELETE FROM mem_atributos WHERE nombre LIKE %s", (f"%{SUFIJO}",))
    conn.commit()


class _Extractor:
    def __init__(self, hechos):
        self.hechos = hechos

    def extraer(self, texto, catalogo, hoy):
        return self.hechos


@pytest.fixture
def entorno():
    conn = get_connection()
    _limpiar(conn)
    repo = RepositorioMemoria(conn)
    cliente = qdrant_en_memoria()
    crear_colecciones(cliente, BASE)
    embedder = EmbedderFalso()
    catalogo = Catalogo(repo, embedder, cliente, BASE)
    catalogo.indexar_atributos()

    def servicio(hechos):
        return ServicioMemoria(repo, catalogo, _Extractor(hechos), embedder, cliente, BASE, umbrales({}),
                               hoy=lambda: date(2026, 11, 15))

    yield SimpleNamespace(repo=repo, cliente=cliente, servicio=servicio, conn=conn)
    _limpiar(conn)
    close_connection()


def _h(entidad="Paco", atributo="alergia", valor="frutos secos", operacion="afirmar", tipo="persona",
       cardinalidad="varios", descripcion=""):
    return {"entidad": entidad, "tipo_entidad": tipo, "atributo": atributo, "tipo_valor": "texto",
            "cardinalidad": cardinalidad, "valor": valor, "operacion": operacion, "descripcion_atributo": descripcion}


def _presion(valor, operacion="afirmar"):
    return _h("coche", f"presion{SUFIJO}", valor, operacion, tipo="vehiculo", cardinalidad="uno",
              descripcion="Presión de las ruedas")


def _fuentes(entorno, user=USER):
    cur = entorno.conn.cursor()
    cur.execute("SELECT * FROM mem_fuentes WHERE user_id = %s ORDER BY id", (user,))
    return list(cur.fetchall())


def _hechos(entorno, user=USER):
    return entorno.repo.hechos_con_nombres(user, solo_vigentes=False)


def _puntos_de_notas(entorno):
    puntos, _ = entorno.cliente.scroll(f"{BASE}_notas", limit=50, with_payload=True)
    return [p.payload["hecho_id"] for p in puntos]


# --- D41: una fuente por llamada, y cada hecho apunta a ella -------------------------------------

def test_guardar_crea_fuente_y_enlaza(entorno):
    servicio = entorno.servicio([_h(), _h(atributo="parentesco", valor="cuñado")])
    servicio.guardar(USER, "Mi cuñado Paco es alérgico a los frutos secos", mensaje="apunta lo de mi cuñado Paco")

    [fuente] = _fuentes(entorno)
    assert fuente["texto"] == "Mi cuñado Paco es alérgico a los frutos secos"
    assert fuente["mensaje"] == "apunta lo de mi cuñado Paco"
    assert fuente["purgada_at"] is None
    hechos = _hechos(entorno)
    assert len(hechos) == 2 and {h["fuente_id"] for h in hechos} == {fuente["id"]}      # comparten fuente


def test_el_mensaje_es_opcional(entorno):
    entorno.servicio([_h()]).guardar(USER, "texto")
    assert _fuentes(entorno)[0]["mensaje"] is None


def test_las_notas_tambien_llevan_su_fuente(entorno):
    entorno.servicio([_h("yo", "nota", "Uso camisetas UV")]).guardar(USER, "Uso camisetas UV", mensaje="m")
    [h] = _hechos(entorno)
    assert h["atributo"] == "nota" and h["fuente_id"] == _fuentes(entorno)[0]["id"]


def test_una_fuente_por_llamada_y_son_del_usuario(entorno):
    entorno.servicio([_h()]).guardar(USER, "uno")
    entorno.servicio([_h(valor="marisco")]).guardar(USER, "dos")
    entorno.servicio([_h()]).guardar(OTRO, "otro")
    assert [f["texto"] for f in _fuentes(entorno)] == ["uno", "dos"]
    assert [f["texto"] for f in _fuentes(entorno, OTRO)] == ["otro"]


def test_fuente_sin_hechos_se_purga(entorno):
    entorno.servicio([]).guardar(USER, "Qué tal estás", mensaje="Qué tal estás, Sebastian")
    [fuente] = _fuentes(entorno)                 # se crea igual, y se purga en el acto: no queda texto sin hecho
    assert fuente["texto"] is None and fuente["mensaje"] is None and fuente["purgada_at"] is not None


def test_fuente_cuyos_hechos_no_cambian_nada_tambien_se_purga(entorno):
    entorno.servicio([_h()]).guardar(USER, "primera")
    entorno.servicio([_h()]).guardar(USER, "segunda: lo mismo")          # sin_cambio: no sale ningun hecho nuevo
    primera, segunda = _fuentes(entorno)
    assert primera["texto"] == "primera" and primera["purgada_at"] is None
    assert segunda["texto"] is None and segunda["purgada_at"] is not None


def test_si_falla_el_extractor_no_se_guarda_ninguna_fuente(entorno):
    servicio = entorno.servicio([])
    servicio._extractor = MagicMock(extraer=MagicMock(side_effect=RuntimeError("api caida")))
    assert servicio.guardar(USER, "algo")["success"] is False
    assert _fuentes(entorno) == []


# --- D42: sustituir no purga ----------------------------------------------------------------------

def test_sustituir_no_purga(entorno):
    entorno.servicio([_presion("2,30 bar")]).guardar(USER, "La presión del coche es 2,30 bar")
    entorno.servicio([_presion("2,4 bar", "corregir")]).guardar(USER, "Me equivoqué: la presión del coche es 2,4 bar")

    assert [f["texto"] for f in _fuentes(entorno)] == ["La presión del coche es 2,30 bar",
                                                       "Me equivoqué: la presión del coche es 2,4 bar"]
    assert sorted(h["valor"] for h in _hechos(entorno)) == ["2,30 bar", "2,4 bar"]       # el historial sigue entero


# --- D42: retirar purga el valor, la cadena y las fuentes -----------------------------------------

def test_retirar_purga_cadena(entorno):
    entorno.servicio([_presion("2,30 bar")]).guardar(USER, "La presión del coche es 2,30 bar")
    entorno.servicio([_presion("2,4 bar", "corregir")]).guardar(USER, "Me equivoqué: es 2,4 bar")
    salida = entorno.servicio([_presion("", "retirar")]).guardar(USER, "Olvida lo de la presión del coche")

    assert [g["operacion"] for g in salida["data"]["guardados"]] == ["retirar"]
    assert salida["data"]["guardados"][0]["valor"] == "2,4 bar"          # la respuesta sigue diciendo que se retiró
    hechos = _hechos(entorno)
    assert len(hechos) == 2                                              # las filas se quedan (nada se borra, D7)
    assert [h["valor"] for h in hechos] == ["", ""]                      # los dos valores, purgados
    assert all(h["valid_to"] is not None for h in hechos)
    assert hechos[0]["superseded_by"] == hechos[1]["id"]                 # y su cadena, sus fechas y su decision
    fuentes = _fuentes(entorno)
    assert len(fuentes) == 3 and all(f["texto"] is None and f["mensaje"] is None and f["purgada_at"] for f in fuentes)
    assert "retirar" in [d["tipo"] for d in entorno.repo.decisiones(USER)]


def test_retirar_purga_una_cadena_de_tres(entorno):
    for valor, op in (("2,2 bar", "afirmar"), ("2,3 bar", "corregir"), ("2,4 bar", "corregir")):
        entorno.servicio([_presion(valor, op)]).guardar(USER, f"presión {valor}")
    entorno.servicio([_presion("", "retirar")]).guardar(USER, "olvida la presión")
    assert [h["valor"] for h in _hechos(entorno)] == ["", "", ""]
    assert all(f["texto"] is None for f in _fuentes(entorno))


def test_retirar_no_purga_fuente_con_vigentes(entorno):
    entorno.servicio([_h(valor="marisco"), _h(valor="frutos secos")]).guardar(
        USER, "Paco es alérgico al marisco y a los frutos secos", mensaje="msg original")
    entorno.servicio([_h(valor="marisco", operacion="retirar")]).guardar(USER, "Olvida lo del marisco de Paco")

    hechos = {h["valor"] or "(purgado)": h for h in _hechos(entorno)}
    assert set(hechos) == {"(purgado)", "frutos secos"}
    assert hechos["(purgado)"]["valid_to"] is not None and hechos["frutos secos"]["valid_to"] is None
    primera = _fuentes(entorno)[0]
    assert primera["texto"] == "Paco es alérgico al marisco y a los frutos secos"   # sigue un hecho vigente
    assert primera["mensaje"] == "msg original" and primera["purgada_at"] is None


def test_retirar_purga_la_fuente_cuando_se_cierra_el_ultimo_vigente(entorno):
    entorno.servicio([_h(valor="marisco"), _h(valor="frutos secos")]).guardar(USER, "las dos")
    entorno.servicio([_h(valor="marisco", operacion="retirar")]).guardar(USER, "olvida marisco")
    assert _fuentes(entorno)[0]["texto"] == "las dos"
    entorno.servicio([_h(valor="frutos secos", operacion="retirar")]).guardar(USER, "olvida frutos secos")
    assert _fuentes(entorno)[0]["texto"] is None and _fuentes(entorno)[0]["purgada_at"] is not None


# --- D42: el vector de una nota ------------------------------------------------------------------

def test_retirar_nota_purga_vector(entorno):
    entorno.servicio([_h("yo", "nota", "Uso camisetas UV")]).guardar(USER, "Uso camisetas UV")
    entorno.servicio([_h("yo", "nota", "Me gusta el cine mudo")]).guardar(USER, "Me gusta el cine mudo")
    assert len(_puntos_de_notas(entorno)) == 2

    # camino exacto: el valor coincide con la nota
    entorno.servicio([_h("yo", "nota", "Uso camisetas UV", "retirar")]).guardar(USER, "Olvida lo de las camisetas UV")

    nota = next(h for h in _hechos(entorno) if h["valid_to"] is not None)
    assert nota["valor"] == ""
    assert nota["id"] not in _puntos_de_notas(entorno) and len(_puntos_de_notas(entorno)) == 1


def test_retirar_nota_por_similitud_tambien_purga_valor_y_vector(entorno):
    """R3 (retirar por similitud) + D42: el mismo cierre, la misma purga."""
    entorno.servicio([_h("yo", "nota", "Uso camisetas UV")]).guardar(USER, "Uso camisetas UV", mensaje="m1")
    olvida = _h("camisetas UV", "nota", "camisetas UV", "retirar", tipo="objeto")
    entorno.servicio([olvida]).guardar(USER, "Olvida lo de las camisetas UV")

    [nota] = _hechos(entorno)
    assert nota["valid_to"] is not None and nota["valor"] == ""
    assert _puntos_de_notas(entorno) == []
    assert all(f["texto"] is None for f in _fuentes(entorno))


def test_la_purga_de_una_nota_arrastra_el_vector_de_su_cadena(entorno):
    """Una nota sustituida y luego retirada: los vectores de las dos desaparecen."""
    antigua = entorno.repo.crear_entidad(USER, "yo", "persona", estado="activo")
    nota = entorno.repo.atributos_por_alias("nota")[0]["id"]
    f1 = entorno.repo.crear_fuente(USER, "primera", None)
    viejo = entorno.repo.anadir_hecho(USER, antigua, nota, "version uno", fuente_id=f1)
    f2 = entorno.repo.crear_fuente(USER, "segunda", None)
    nuevo = entorno.repo.sustituir_hecho(USER, viejo, antigua, nota, "version dos", fuente_id=f2)
    servicio = entorno.servicio([])
    servicio._embeber_nota(USER, viejo, "version uno")
    servicio._embeber_nota(USER, nuevo, "version dos")
    assert sorted(_puntos_de_notas(entorno)) == sorted([viejo, nuevo])

    servicio._retirar(USER, nuevo)

    assert _puntos_de_notas(entorno) == []
    assert [h["valor"] for h in _hechos(entorno)] == ["", ""]


# --- atomicidad y fallos --------------------------------------------------------------------------

def test_retirar_y_purgar_es_una_sola_transaccion(entorno):
    hid = entorno.repo.anadir_hecho(USER, entorno.repo.crear_entidad(USER, "Paco", "persona", estado="activo"),
                                    entorno.repo.atributos_por_alias("alergia")[0]["id"], "marisco",
                                    fuente_id=entorno.repo.crear_fuente(USER, "texto", "msg"))

    class FallaAlPurgarLaFuente:
        def __init__(self, db):
            self._db = db

        def cursor(self):
            cur = self._db.cursor()
            original = cur.execute

            def execute(sql, params=None):
                if sql.lstrip().upper().startswith("UPDATE MEM_FUENTES"):
                    raise RuntimeError("falla justo al purgar la fuente")
                return original(sql, params)

            cur.execute = execute
            return cur

        def __getattr__(self, nombre):
            return getattr(self._db, nombre)

    repo_roto = RepositorioMemoria(FallaAlPurgarLaFuente(entorno.conn))
    with pytest.raises(RuntimeError):
        repo_roto.retirar_y_purgar(USER, hid)

    h = entorno.repo.hecho(hid)                      # ni cerrado ni borrado el valor ni purgada la fuente
    assert h["valid_to"] is None and h["valor"] == "marisco"
    assert _fuentes(entorno)[0]["texto"] == "texto"


def test_si_falla_qdrant_al_borrar_el_vector_la_retirada_sigue_y_el_aviso_no_lleva_texto(entorno):
    entorno.servicio([_h("yo", "nota", "texto-secreto-777")]).guardar(USER, "texto-secreto-777")
    servicio = entorno.servicio([_h("yo", "nota", "texto-secreto-777", "retirar")])
    servicio._qdrant = MagicMock(delete=MagicMock(side_effect=RuntimeError("qdrant caido")))

    with patch("core.memoria.servicio.logger") as log:
        salida = servicio.guardar(USER, "olvida texto-secreto-777")

    assert salida["success"] is True and [g["operacion"] for g in salida["data"]["guardados"]] == ["retirar"]
    [nota] = _hechos(entorno)
    assert nota["valid_to"] is not None and nota["valor"] == ""                  # SQL manda: ya esta retirada y purgada
    avisos = " ".join(str(c) for c in log.warning.mock_calls)
    assert "qdrant" in avisos.lower() or "vector" in avisos.lower()
    assert "texto-secreto-777" not in " ".join(str(c) for c in log.mock_calls)


def test_retirar_algo_que_no_existe_no_purga_nada(entorno):
    entorno.servicio([_h()]).guardar(USER, "Paco, frutos secos")
    entorno.servicio([_h(entidad="Nadie", valor="x", operacion="retirar")]).guardar(USER, "olvida lo de Nadie")
    assert [h["valor"] for h in _hechos(entorno)] == ["frutos secos"]
    assert _fuentes(entorno)[0]["texto"] == "Paco, frutos secos"


# --- lo purgado no se cuenta despues ---------------------------------------------------------------

def test_el_historial_no_ensena_lo_olvidado(entorno):
    entorno.servicio([_h(valor="marisco"), _h(valor="frutos secos")]).guardar(USER, "las dos")
    entorno.servicio([_h(valor="marisco", operacion="retirar")]).guardar(USER, "olvida marisco")

    salida = entorno.servicio([]).consultar(USER, "alergias", entidad="Paco", atributo="alergia", historial=True)

    assert [h["valor"] for h in salida["hechos"]] == ["frutos secos"]
    assert salida["historial"] == []              # lo olvidado ya no tiene texto: no sale una entrada vacia
