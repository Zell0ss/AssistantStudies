"""H4 (fase 2, plan §3 H4.1): migrar los hechos de Sprint 3 (colección plana de Qdrant) a MariaDB. Sin API.

La colección se lee con un Qdrant falso que SOLO sabe `scroll`: cualquier otra llamada (una escritura) falla.
La BD es `sebastian_test` (D25)."""
from types import SimpleNamespace

import pytest

from core.memoria.repositorio import RepositorioMemoria
from db.connection import close_connection, get_connection
from scripts.memoria.migrar_sprint3 import main, migrar

USER = "test_migrar_a"
OTRO = "test_migrar_b"
ATRIBUTO_NUEVO = "presion_neumaticos"

ALERGIA = "Tengo alergia al ácido acetilsalicílico"
CAMISETAS = "Sebastian usa camisetas de protección UV para bañarse"       # el sujeto está mal: lo dijo Josem de sí mismo
PRESION = "La presión de las ruedas del coche es 2,30 bares"
AJENO = "Un dato que el mapa no conoce"


class QdrantSoloLectura:
    """Solo `scroll`, paginado de 2 en 2 como haría un Qdrant real. Todo lo demás: AttributeError."""

    def __init__(self, textos):
        self._puntos = [SimpleNamespace(id=i, payload={"content": t, "tags": []}) for i, t in enumerate(textos)]
        self.llamadas = []

    def scroll(self, collection_name, limit=10, offset=None, with_payload=True, with_vectors=False, **kw):
        self.llamadas.append(("scroll", collection_name))
        ini = offset or 0
        lote = self._puntos[ini:ini + 2]
        return lote, (ini + 2 if ini + 2 < len(self._puntos) else None)


def _limpiar(conn):
    cur = conn.cursor()
    u = (USER, OTRO)
    cur.execute("DELETE FROM mem_decisiones WHERE user_id IN (%s, %s)", u)
    cur.execute("UPDATE mem_hechos SET superseded_by = NULL WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_hechos WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_fuentes WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_entidad_alias WHERE entidad_id IN (SELECT id FROM mem_entidades WHERE user_id IN (%s, %s))", u)
    cur.execute("DELETE FROM mem_entidades WHERE user_id IN (%s, %s)", u)
    # el atributo lo crea la migracion (y lo crea tambien el golden del extractor): no puede quedar entre pruebas
    cur.execute("DELETE FROM mem_hechos WHERE atributo_id IN (SELECT id FROM mem_atributos WHERE nombre = %s)", (ATRIBUTO_NUEVO,))
    cur.execute("DELETE FROM mem_atributo_alias WHERE atributo_id IN (SELECT id FROM mem_atributos WHERE nombre = %s)", (ATRIBUTO_NUEVO,))
    cur.execute("DELETE FROM mem_atributos WHERE nombre = %s", (ATRIBUTO_NUEVO,))
    conn.commit()


@pytest.fixture
def conn():
    c = get_connection()
    _limpiar(c)
    yield c
    _limpiar(c)
    close_connection()


def _hechos(conn, user=USER):
    return RepositorioMemoria(conn).hechos_con_nombres(user, solo_vigentes=False)


def _todo():
    return QdrantSoloLectura([ALERGIA, CAMISETAS, PRESION, PRESION, AJENO])


def test_migrar_sprint3_mapa(conn):
    """Los 3 hechos, el duplicado descartado y el sujeto corregido (plan §3 H4.1). H3-revision §5.4: además, la alergia
    al ácido acetilsalicílico queda como `alergia`, porque con R6 es memoria."""
    resultado = migrar(conn, _todo(), "sebastian_memory", USER)

    hechos = {(h["entidad"], h["atributo"]): h for h in _hechos(conn)}
    assert set(hechos) == {("yo", "alergia"), ("yo", "nota"), ("coche", ATRIBUTO_NUEVO)}
    assert hechos[("yo", "alergia")]["valor"] == "ácido acetilsalicílico"
    assert hechos[("yo", "nota")]["valor"] == "Uso camisetas UV para bañarme"       # sujeto corregido: «Uso», no «Sebastian usa»
    assert hechos[("coche", ATRIBUTO_NUEVO)]["valor"] == "2,30 bar"
    for h in hechos.values():                                                         # H3-revision §5.4: no se inventa fuente
        assert h["origen"] == "migracion" and h["fuente_id"] is None and h["valid_to"] is None
    assert len(_hechos(conn)) == 3                                                    # el duplicado de la presion, descartado
    assert resultado["descartados"] == 1 and resultado["sin_mapa"] == [AJENO]


def test_migrar_sprint3_crea_la_entidad_coche_y_el_atributo_nuevo_activo(conn):
    migrar(conn, _todo(), "sebastian_memory", USER)
    repo = RepositorioMemoria(conn)
    [coche] = repo.entidades_por_alias(USER, "coche")
    assert (coche["tipo"], coche["estado"], coche["origen"]) == ("vehiculo", "activo", "migracion")
    [attr] = repo.atributos_por_alias(ATRIBUTO_NUEVO)
    assert (attr["estado"], attr["cardinalidad"], attr["tipos_entidad"], attr["tipo_valor"]) == (
        "activo", "uno", "vehiculo", "numero")
    assert repo.entidad_usuario(USER) == repo.entidades_por_alias(USER, "yo")[0]["id"]     # «yo» es la entidad del usuario


def test_migrar_sprint3_idempotente(conn):
    migrar(conn, _todo(), "sebastian_memory", USER)
    antes = [(h["id"], h["valor"]) for h in _hechos(conn)]
    segunda = migrar(conn, _todo(), "sebastian_memory", USER)

    assert [(h["id"], h["valor"]) for h in _hechos(conn)] == antes                    # ni filas nuevas ni cambiadas
    assert segunda["escritos"] == 0 and segunda["ya_estaban"] == 3
    assert len(RepositorioMemoria(conn).entidades_por_alias(USER, "coche")) == 1


def test_migrar_sprint3_no_resucita_lo_que_el_usuario_olvido(conn):
    """Si tras migrar el usuario pidió olvidar uno (D42: queda cerrado y con el valor en ''), volver a ejecutar no lo recrea."""
    migrar(conn, _todo(), "sebastian_memory", USER)
    repo = RepositorioMemoria(conn)
    nota = next(h for h in _hechos(conn) if h["atributo"] == "nota")
    repo.retirar_y_purgar(USER, nota["id"])

    migrar(conn, _todo(), "sebastian_memory", USER)

    assert [h["valor"] for h in _hechos(conn) if h["atributo"] == "nota"] == [""]
    assert len(_hechos(conn)) == 3


def test_migrar_sprint3_no_escribe_en_qdrant(conn):
    qdrant = _todo()                                  # solo tiene `scroll`: una escritura lanzaria AttributeError
    migrar(conn, qdrant, "sebastian_memory", USER)
    assert {l[0] for l in qdrant.llamadas} == {"scroll"}
    assert {l[1] for l in qdrant.llamadas} == {"sebastian_memory"}                     # la coleccion base, no las nuevas


def test_migrar_sprint3_lee_todas_las_paginas(conn):
    textos = [AJENO] * 3 + [ALERGIA]                  # el hecho esta en la 2.ª pagina
    migrar(conn, QdrantSoloLectura(textos), "sebastian_memory", USER)
    assert [h["atributo"] for h in _hechos(conn)] == ["alergia"]


def test_migrar_sprint3_dry_run_no_escribe_nada_y_cuenta_lo_que_haria(conn, capsys):
    resultado = migrar(conn, _todo(), "sebastian_memory", USER, dry_run=True)
    assert _hechos(conn) == []
    assert RepositorioMemoria(conn).entidades_por_alias(USER, "coche") == []
    assert RepositorioMemoria(conn).atributos_por_alias(ATRIBUTO_NUEVO) == []
    assert resultado["escritos"] == 3 and resultado["dry_run"] is True
    salida = capsys.readouterr().out
    assert "Uso camisetas UV para bañarme" in salida and "2,30 bar" in salida          # enseña lo que haria
    assert CAMISETAS in salida                                                         # y de que texto sale (original -> migrado)


def test_migrar_sprint3_es_del_usuario_que_se_le_dice(conn):
    migrar(conn, _todo(), "sebastian_memory", USER)
    assert _hechos(conn, OTRO) == []


def test_main_se_niega_con_una_base_de_produccion_sin_el_flag(conn, capsys):
    qdrant = _todo()
    codigo = main([], base="sebastian_memory", nombre_bd="sebastian_db", db=conn, qdrant=qdrant, user_id=USER)
    assert codigo == 2 and qdrant.llamadas == [] and _hechos(conn) == []
    assert "--produccion" in capsys.readouterr().err


def test_main_con_el_flag_migra_y_con_base_de_test_no_hace_falta(conn):
    assert main(["--produccion"], base="sebastian_memory", nombre_bd="sebastian_db", db=conn, qdrant=_todo(),
                user_id=USER) == 0
    assert len(_hechos(conn)) == 3
    _limpiar(conn)
    assert main([], base="sebastian_memory_test", nombre_bd="sebastian_test", db=conn, qdrant=_todo(),
                user_id=USER) == 0
    assert len(_hechos(conn)) == 3
