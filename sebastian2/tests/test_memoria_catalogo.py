"""H1 (fase 2): esquema, semillas, repositorio y catalogo de la memoria (D33, D35, D38)."""
import re
from pathlib import Path

import pytest

from core.memoria.catalogo import Catalogo
from core.memoria.embedder import Embedder
from core.memoria.repositorio import RepositorioMemoria
from db.connection import close_connection, get_connection
from scripts.memoria.crear_colecciones import crear_colecciones
from tests.fakes_memoria import EmbedderFalso, qdrant_en_memoria

RAIZ = Path(__file__).resolve().parent.parent
USER = "test_mem_catalogo_a"
OTRO = "test_mem_catalogo_b"
ATRIBUTOS_DE_PRUEBA = ("presion_neumaticos_test", "atributo_pending_test")


def _limpiar(conn):
    cur = conn.cursor()
    ids = "SELECT id FROM mem_entidades WHERE user_id IN (%s, %s)"
    cur.execute(f"DELETE FROM mem_hechos WHERE user_id IN (%s, %s)", (USER, OTRO))
    cur.execute(f"DELETE FROM mem_entidad_alias WHERE entidad_id IN ({ids})", (USER, OTRO))
    cur.execute("DELETE FROM mem_entidades WHERE user_id IN (%s, %s)", (USER, OTRO))
    marcas = ",".join(["%s"] * len(ATRIBUTOS_DE_PRUEBA))
    cur.execute(f"DELETE FROM mem_atributo_alias WHERE atributo_id IN"
                f" (SELECT id FROM mem_atributos WHERE nombre IN ({marcas}))", ATRIBUTOS_DE_PRUEBA)
    cur.execute(f"DELETE FROM mem_atributos WHERE nombre IN ({marcas})", ATRIBUTOS_DE_PRUEBA)
    conn.commit()


@pytest.fixture
def repo():
    conn = get_connection()
    _limpiar(conn)
    yield RepositorioMemoria(conn)
    _limpiar(conn)
    close_connection()


def _sentencias(ruta):
    sql = re.sub(r"--[^\n]*", "", Path(ruta).read_text())
    return [s.strip() for s in sql.split(";") if s.strip()]


def _contar(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM mem_atributos")
    atributos = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM mem_atributo_alias")
    return atributos, cur.fetchone()["n"]


# --- Esquema y semillas -------------------------------------------------------------------

def test_semillas_idempotentes():
    conn = get_connection()
    antes = _contar(conn)
    cur = conn.cursor()
    for _ in range(2):
        for sentencia in _sentencias(RAIZ / "db" / "migrations" / "011_memoria_semillas.sql"):
            cur.execute(sentencia)
        conn.commit()
    assert _contar(conn) == antes
    close_connection()


def test_semillas_son_las_del_plan(repo):
    nombres = {a["nombre"] for a in repo.listar_atributos(estado="activo")}
    assert {"nota", "alergia", "cumpleanos", "parentesco", "preferencia",
            "estado", "host", "stack", "repo", "db"} <= nombres
    contrato = {a["nombre"] for a in repo.listar_atributos() if a["fuente"] == "contrato_vault"}
    assert contrato == {"estado", "host", "stack", "repo", "db"}


def test_semillas_sin_entidades(repo):
    cur = repo._db.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM mem_entidades WHERE origen = 'semilla'")
    assert cur.fetchone()["n"] == 0


# --- Repositorio: entidades por usuario (D33) ---------------------------------------------

def test_entidad_por_usuario(repo):
    a = repo.crear_entidad(USER, "Paco", "persona")
    b = repo.crear_entidad(OTRO, "Paco", "persona")
    assert a != b

    assert [e["id"] for e in repo.entidades_por_alias(USER, "el paco")] == [a]
    assert [e["id"] for e in repo.entidades_por_alias(OTRO, "Paco")] == [b]


def test_alias_de_un_usuario_no_resuelve_para_otro(repo):
    a = repo.crear_entidad(USER, "Paco", "persona")
    repo.anadir_alias_entidad(a, "mi cuñado")

    assert [e["id"] for e in repo.entidades_por_alias(USER, "cuñado")] == [a]
    assert repo.entidades_por_alias(OTRO, "cuñado") == []


def test_alias_distingue_n_de_enie(repo):
    a = repo.crear_entidad(USER, "Año nuevo", "otro")
    assert repo.entidades_por_alias(USER, "ano nuevo") == []
    assert [e["id"] for e in repo.entidades_por_alias(USER, "año nuevo")] == [a]


def test_yo_se_crea_una_vez(repo):
    primero = repo.entidad_usuario(USER, username="Josem")
    segundo = repo.entidad_usuario(USER, username="Josem")
    assert primero == segundo
    yo = repo.entidad(primero)
    assert yo["es_usuario"] and yo["estado"] == "activo"
    for alias in ("yo", "mi", "me", "Josem"):
        assert [e["id"] for e in repo.entidades_por_alias(USER, alias)] == [primero]
    # el «yo» de otro usuario es otra entidad
    assert repo.entidad_usuario(OTRO, username="Pepa") != primero


def test_atributos_alias_y_pending(repo):
    pid = repo.crear_atributo("atributo_pending_test", "Descripcion de prueba")
    assert repo.atributo(pid)["estado"] == "pending"
    repo.anadir_alias_atributo(pid, "Mis Pruebas")
    assert [a["id"] for a in repo.atributos_por_alias("pruebas")] == [pid]
    # un atributo semilla se resuelve por alias comun
    assert [a["nombre"] for a in repo.atributos_por_alias("alergias")] == ["alergia"]


# --- Catalogo semantico (D35) con embedder falso ------------------------------------------

@pytest.fixture
def catalogo(repo):
    cliente = qdrant_en_memoria()
    crear_colecciones(cliente, "mem_test")
    return Catalogo(repo, EmbedderFalso(), cliente, "mem_test"), repo


def test_embedder_es_intercambiable(catalogo):
    cat, repo = catalogo
    assert isinstance(cat._embedder, Embedder)
    pid = repo.crear_atributo("presion_neumaticos_test", "presion de los neumaticos de un vehiculo",
                              estado="activo")
    cat.indexar_atributos()

    candidatos = cat.buscar_atributos("presion de los neumaticos del coche")

    assert candidatos[0]["nombre"] == "presion_neumaticos_test"
    assert candidatos[0]["id"] == pid
    assert candidatos[0]["score"] > 0.5


def test_catalogo_embebe_descripciones_no_alias(catalogo):
    cat, repo = catalogo
    repo.crear_atributo("presion_neumaticos_test", "presion de los neumaticos", estado="activo")
    repo.anadir_alias_atributo(repo.atributos_por_alias("presion neumaticos test")[0]["id"], "ruedas")
    embedder = cat._embedder

    cat.indexar_atributos()

    textos = [t for llamada in embedder.llamadas for t in llamada]
    assert "presion de los neumaticos" in textos
    assert "ruedas" not in textos


def test_catalogo_ordena_y_da_margen(catalogo):
    cat, repo = catalogo
    cat.indexar_atributos()
    candidatos = cat.buscar_atributos("alergia a la penicilina", k=3)
    puntuaciones = [c["score"] for c in candidatos]
    assert puntuaciones == sorted(puntuaciones, reverse=True)
    assert candidatos[0]["nombre"] == "alergia"
    assert Catalogo.margen(candidatos) == pytest.approx(puntuaciones[0] - puntuaciones[1])
    assert Catalogo.margen(candidatos[:1]) == pytest.approx(candidatos[0]["score"])
    assert Catalogo.margen([]) == 0.0


def test_catalogo_de_entidades_filtra_por_usuario(catalogo):
    cat, repo = catalogo
    a = repo.crear_entidad(USER, "Paco", "persona", descripcion="mi cuñado")
    b = repo.crear_entidad(OTRO, "Paco", "persona", descripcion="mi cuñado")
    cat.indexar_entidad(repo.entidad(a))
    cat.indexar_entidad(repo.entidad(b))

    de_user = cat.buscar_entidades(USER, "Paco mi cuñado")
    de_otro = cat.buscar_entidades(OTRO, "Paco mi cuñado")

    assert [c["id"] for c in de_user] == [a]
    assert [c["id"] for c in de_otro] == [b]


def test_indexar_es_idempotente(catalogo):
    cat, repo = catalogo
    cat.indexar_atributos()
    n1 = cat._qdrant.count("mem_test_catalogo").count
    cat.indexar_atributos()
    assert cat._qdrant.count("mem_test_catalogo").count == n1
