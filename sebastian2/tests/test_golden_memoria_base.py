"""H3 (plan §3 H3.2): el harness de goldens siembra y limpia la memoria nueva en MariaDB. Sin API.

Prueba las piezas de `tests/golden/memoria_base.py` (lo que la fixture de los goldens y los escenarios usan),
contra `sebastian_test`, para que un fallo del harness no se descubra en una pasada de pago."""
import pytest

from core.memoria.repositorio import RepositorioMemoria
from db.connection import close_connection, get_connection
from tests.golden.memoria_base import (
    decisiones, exigir_bd_de_test, fuentes, hechos, limpiar_atributos_de_conversacion, limpiar_memoria,
    sembrar_memoria_base,
)

A = "test_golden_base_a"
B = "test_golden_base_b"
AJENO = "test_golden_base_ajeno"
ATRIBUTO = "atributo_golden_base_test"


@pytest.fixture
def conn():
    c = get_connection()
    limpiar_memoria(c, A, B, AJENO)
    _borrar_atributo(c)
    yield c
    limpiar_memoria(c, A, B, AJENO)
    _borrar_atributo(c)
    close_connection()


def _borrar_atributo(c):
    cur = c.cursor()
    cur.execute("DELETE FROM mem_atributo_alias WHERE atributo_id IN (SELECT id FROM mem_atributos WHERE nombre = %s)",
                (ATRIBUTO,))
    cur.execute("DELETE FROM mem_atributos WHERE nombre = %s", (ATRIBUTO,))
    c.commit()


def test_la_memoria_base_son_los_tres_hechos_de_siempre_mas_el_yo(conn):
    sembrar_memoria_base(conn, A)
    repo = RepositorioMemoria(conn)

    filas = repo.hechos_con_nombres(A)
    assert sorted((f["entidad"], f["atributo"]) for f in filas) == [
        ("Paco", "alergia"), ("Rebe", "cumpleanos"), ("yo", "preferencia")]
    paco = next(f for f in filas if f["entidad"] == "Paco")
    assert paco["valor"] == "frutos secos"           # lo que el golden #21 tiene que encontrar
    assert repo.entidades_por_alias(A, "yo")[0]["es_usuario"]
    assert repo.entidades_por_alias(A, "paco")[0]["tipo"] == "persona"


def test_sembrar_dos_veces_no_duplica(conn):
    sembrar_memoria_base(conn, A)
    limpiar_memoria(conn, A)
    sembrar_memoria_base(conn, A)
    assert len(RepositorioMemoria(conn).hechos_con_nombres(A)) == 3


def test_limpiar_solo_toca_a_esos_usuarios(conn):
    sembrar_memoria_base(conn, A)
    sembrar_memoria_base(conn, AJENO)
    repo = RepositorioMemoria(conn)
    repo.registrar_decision(A, "sin_cambio", {}, "x")

    limpiar_memoria(conn, A)

    assert repo.hechos_con_nombres(A, solo_vigentes=False) == [] and repo.decisiones(A) == []
    assert repo.listar_entidades(A) == []
    assert len(repo.hechos_con_nombres(AJENO)) == 3


def test_limpiar_tambien_borra_las_fuentes_y_no_viola_su_clave_ajena(conn):
    repo = RepositorioMemoria(conn)
    e = repo.crear_entidad(A, "Paco", "persona", estado="activo")
    fuente = repo.crear_fuente(A, "texto", "mensaje")
    repo.anadir_hecho(A, e, repo.atributos_por_alias("alergia")[0]["id"], "marisco", fuente_id=fuente)
    repo.crear_fuente(AJENO, "de otro", None)

    limpiar_memoria(conn, A)

    assert repo.fuente(fuente) is None
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM mem_fuentes WHERE user_id = %s", (AJENO,))
    assert cur.fetchone()["n"] == 1                       # solo toca a esos usuarios


def test_limpiar_con_hechos_sustituidos_no_viola_la_clave_ajena(conn):
    repo = RepositorioMemoria(conn)
    e = repo.crear_entidad(A, "coche", "vehiculo", estado="activo")
    a = repo.atributos_por_alias("nota")[0]["id"]
    viejo = repo.anadir_hecho(A, e, a, "uno")
    repo.sustituir_hecho(A, viejo, e, a, "dos")
    limpiar_memoria(conn, A)
    assert repo.hechos_con_nombres(A, solo_vigentes=False) == []


def test_hechos_filtra_por_alias_de_entidad_y_nombre_de_atributo(conn):
    sembrar_memoria_base(conn, A)
    assert [h["valor"] for h in hechos(conn, A, entidad="Paco", atributo="alergia")] == ["frutos secos"]
    assert [h["atributo"] for h in hechos(conn, A, entidad="paco")] == ["alergia"]
    assert len(hechos(conn, A)) == 3
    assert hechos(conn, A, entidad="Nadie") == []


def test_hechos_distingue_vigentes_de_cerrados(conn):
    sembrar_memoria_base(conn, A)
    repo = RepositorioMemoria(conn)
    repo.retirar_hecho(hechos(conn, A, entidad="Paco")[0]["id"])
    assert hechos(conn, A, entidad="Paco", vigentes=True) == []
    assert len(hechos(conn, A, entidad="Paco", vigentes=False)) == 1
    assert len(hechos(conn, A, entidad="Paco")) == 1            # sin filtro: vigentes y cerrados


def test_fuentes_devuelve_las_del_usuario_en_orden_y_con_lo_purgado_a_none(conn):
    repo = RepositorioMemoria(conn)
    primera = repo.crear_fuente(A, "uno", "mensaje uno")
    segunda = repo.crear_fuente(A, "dos", None)
    repo.crear_fuente(B, "de otro", None)
    repo.purgar_fuente_sin_hechos(segunda)                       # sin hechos: se purga
    assert [(f["id"], f["texto"], f["mensaje"]) for f in fuentes(conn, A)] == [
        (primera, "uno", "mensaje uno"), (segunda, None, None)]      # en orden; la purgada, con texto y mensaje a None
    assert fuentes(conn, A)[0]["purgada_at"] is None and fuentes(conn, A)[1]["purgada_at"] is not None
    assert [f["texto"] for f in fuentes(conn, B)] == ["de otro"]


def test_decisiones_devuelve_las_del_usuario(conn):
    RepositorioMemoria(conn).registrar_decision(A, "nota", {"regla": "x"}, "d")
    assert [d["tipo"] for d in decisiones(conn, A)] == ["nota"] and decisiones(conn, B) == []


def test_limpiar_atributos_borra_los_de_conversacion_sin_hechos_y_deja_el_resto(conn):
    repo = RepositorioMemoria(conn)
    repo.crear_atributo(ATRIBUTO, "Atributo de prueba del harness")                  # fuente: conversacion
    usado = repo.crear_atributo(ATRIBUTO + "_usado", "Con un hecho", fuente="conversacion")
    e = repo.crear_entidad(A, "algo", "objeto", estado="activo")
    repo.anadir_hecho(A, e, usado, "v")
    try:
        limpiar_atributos_de_conversacion(conn)
        assert repo.atributos_por_alias(ATRIBUTO) == []                               # sin hechos: fuera
        assert repo.atributos_por_alias(ATRIBUTO + "_usado") != []                    # con hechos: se queda
        assert repo.atributos_por_alias("alergia") != []                              # una semilla: se queda
    finally:
        limpiar_memoria(conn, A)
        cur = conn.cursor()
        cur.execute("DELETE FROM mem_atributo_alias WHERE atributo_id = %s", (usado,))
        cur.execute("DELETE FROM mem_atributos WHERE id = %s", (usado,))
        conn.commit()


def test_el_harness_se_niega_si_la_bd_no_es_la_de_test():
    class BdAjena:
        def cursor(self):
            return self

        def execute(self, *_):
            pass

        def fetchone(self):
            return {"db": "sebastian_db"}

        def close(self):
            pass

    with pytest.raises(RuntimeError, match="sebastian_db"):
        exigir_bd_de_test(BdAjena())
    with pytest.raises(RuntimeError):
        limpiar_memoria(BdAjena(), A)           # todas las escrituras del harness pasan por la guarda
