"""H3 (fase 2, plan §2.5 y §3 H3.5, D36): el indice de lo que Sebastian sabe del usuario, para el planner.
Nombres de entidades y atributos, nunca valores. Contra `sebastian_test`."""
import pytest

from core.memoria.catalogo import indice_memoria
from core.memoria.repositorio import RepositorioMemoria
from db.connection import close_connection, get_connection

USER = "test_mem_indice_a"
OTRO = "test_mem_indice_b"
CABECERA = "Lo que me consta de ti (nombres, sin valores; usa search_memory para los valores):"


def _limpiar(conn):
    cur = conn.cursor()
    u = (USER, OTRO)
    cur.execute("UPDATE mem_hechos SET superseded_by = NULL WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_hechos WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_entidad_alias WHERE entidad_id IN"
                " (SELECT id FROM mem_entidades WHERE user_id IN (%s, %s))", u)
    cur.execute("DELETE FROM mem_entidades WHERE user_id IN (%s, %s)", u)
    conn.commit()


@pytest.fixture
def repo():
    conn = get_connection()
    _limpiar(conn)
    yield RepositorioMemoria(conn)
    _limpiar(conn)
    close_connection()


def _hecho(repo, user, entidad, tipo, atributo, valor):
    e = repo.entidades_por_alias(user, entidad)
    eid = e[0]["id"] if e else repo.crear_entidad(user, entidad, tipo, estado="activo")
    return repo.anadir_hecho(user, eid, repo.atributos_por_alias(atributo)[0]["id"], valor)


def test_formato_del_plan(repo):
    yo = repo.entidad_usuario(USER, "Josem")
    repo.anadir_hecho(USER, yo, repo.atributos_por_alias("preferencia")[0]["id"], "el café sin azúcar")
    repo.anadir_hecho(USER, yo, repo.atributos_por_alias("alergia")[0]["id"], "polen")
    _hecho(repo, USER, "Paco", "persona", "parentesco", "cuñado")
    _hecho(repo, USER, "Paco", "persona", "alergia", "frutos secos")

    lineas = indice_memoria(repo, USER).splitlines()
    assert lineas[0] == CABECERA
    assert sorted(lineas[1:]) == ["- Josem (tú): alergia, preferencia", "- Paco (persona): alergia, parentesco"]


def test_indice_sin_valores(repo):
    _hecho(repo, USER, "Paco", "persona", "alergia", "valor-secreto-123")
    _hecho(repo, USER, "Paco", "persona", "nota", "Una nota con texto-secreto-456 dentro")
    texto = indice_memoria(repo, USER)
    assert "valor-secreto-123" not in texto and "texto-secreto-456" not in texto
    assert "Paco" in texto and "alergia" in texto and "nota" in texto     # los nombres si


def test_indice_max_40(repo):
    for i in range(45):
        _hecho(repo, USER, f"Persona{i:02d}", "persona", "alergia", f"v{i}")
    lineas = indice_memoria(repo, USER).splitlines()
    assert len(lineas) == 1 + 40                                           # cabecera + 40
    assert "Persona44" in "\n".join(lineas) and "Persona04" not in "\n".join(lineas)   # caen las mas antiguas


def test_se_ordena_por_el_ultimo_hecho(repo):
    _hecho(repo, USER, "Antigua", "persona", "alergia", "a")
    _hecho(repo, USER, "Media", "persona", "alergia", "b")
    _hecho(repo, USER, "Reciente", "persona", "alergia", "c")
    _hecho(repo, USER, "Antigua", "persona", "parentesco", "d")            # Antigua vuelve a ser la ultima
    nombres = [l.split(" (")[0][2:] for l in indice_memoria(repo, USER).splitlines()[1:]]
    assert nombres == ["Antigua", "Reciente", "Media"]


def test_sin_nada_no_hay_seccion(repo):
    assert indice_memoria(repo, USER) == ""
    repo.entidad_usuario(USER)                                             # el «yo» sin hechos tampoco
    assert indice_memoria(repo, USER) == ""


def test_solo_cuentan_los_hechos_vigentes(repo):
    hid = _hecho(repo, USER, "Paco", "persona", "alergia", "marisco")
    _hecho(repo, USER, "Paco", "persona", "parentesco", "cuñado")
    _hecho(repo, USER, "Ana", "persona", "alergia", "polen")
    repo.retirar_hecho(hid)
    texto = indice_memoria(repo, USER)
    assert "- Paco (persona): parentesco" in texto and "- Ana (persona): alergia" in texto
    assert "alergia" not in texto.split("Paco")[1].splitlines()[0]         # el atributo retirado no consta
    hid_ana = repo.hechos_vigentes(USER, repo.entidades_por_alias(USER, "ana")[0]["id"],
                                   repo.atributos_por_alias("alergia")[0]["id"])[0]["id"]
    repo.retirar_hecho(hid_ana)
    assert "Ana" not in indice_memoria(repo, USER)                         # sin hechos vigentes, sin linea


def test_solo_del_usuario(repo):
    _hecho(repo, OTRO, "Marisol", "persona", "alergia", "polen")
    assert indice_memoria(repo, USER) == ""
    assert "Marisol" in indice_memoria(repo, OTRO)


def test_los_proyectos_del_vault_se_marcan(repo):
    _hecho(repo, USER, "proyecto-prueba", "proyecto", "estado", "pausado")
    _hecho(repo, USER, "saxhero", "proyecto", "estado", "activo")
    proyectos = {"proyecto-prueba": {"estado": "stable"}}
    lineas = indice_memoria(repo, USER, proyectos).splitlines()
    assert "- proyecto-prueba (proyecto, vault): estado" in lineas
    assert "- saxhero (proyecto): estado" in lineas
    assert "(proyecto, vault)" not in indice_memoria(repo, USER)           # sin vault, sin marca
