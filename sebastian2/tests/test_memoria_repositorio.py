"""H2 (fase 2): hechos con vigencia y registro de decisiones, contra sebastian_test (D7, D38)."""
import pytest

from core.memoria.repositorio import RepositorioMemoria
from db.connection import close_connection, get_connection

USER = "test_mem_repo_a"


def _limpiar(conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM mem_decisiones WHERE user_id = %s", (USER,))
    cur.execute("UPDATE mem_hechos SET superseded_by = NULL WHERE user_id = %s", (USER,))
    cur.execute("DELETE FROM mem_hechos WHERE user_id = %s", (USER,))
    cur.execute("DELETE FROM mem_entidad_alias WHERE entidad_id IN"
                " (SELECT id FROM mem_entidades WHERE user_id = %s)", (USER,))
    cur.execute("DELETE FROM mem_entidades WHERE user_id = %s", (USER,))
    conn.commit()


@pytest.fixture
def repo():
    conn = get_connection()
    _limpiar(conn)
    yield RepositorioMemoria(conn)
    _limpiar(conn)
    close_connection()


@pytest.fixture
def contexto(repo):
    entidad = repo.crear_entidad(USER, "coche", "vehiculo", estado="activo")
    atributo = repo.atributos_por_alias("nota")[0]["id"]   # semilla, cardinalidad varios
    return repo, entidad, atributo


def _filas(repo):
    cur = repo._db.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM mem_hechos WHERE user_id = %s", (USER,))
    return cur.fetchone()["n"]


def test_anadir_y_vigentes(contexto):
    repo, entidad, atributo = contexto
    hid = repo.anadir_hecho(USER, entidad, atributo, "2,2 bar", confianza=0.9)
    vigentes = repo.hechos_vigentes(USER, entidad, atributo)
    assert [(h["id"], h["valor"], h["valid_to"]) for h in vigentes] == [(hid, "2,2 bar", None)]
    assert float(vigentes[0]["confianza"]) == pytest.approx(0.9)


def test_vigentes_solo_del_usuario(contexto):
    repo, entidad, atributo = contexto
    repo.anadir_hecho(USER, entidad, atributo, "x")
    assert repo.hechos_vigentes("otro_usuario", entidad, atributo) == []


def test_superseded_by_apunta_al_nuevo(contexto):
    repo, entidad, atributo = contexto
    viejo = repo.anadir_hecho(USER, entidad, atributo, "2,2 bar")
    nuevo = repo.sustituir_hecho(USER, viejo, entidad, atributo, "2,4 bar")

    cerrado = repo.hecho(viejo)
    assert cerrado["superseded_by"] == nuevo
    assert cerrado["valid_to"] is not None
    assert [h["id"] for h in repo.hechos_vigentes(USER, entidad, atributo)] == [nuevo]
    assert repo.hecho(nuevo)["valid_to"] is None


def test_sustitucion_es_atomica(contexto):
    repo, entidad, atributo = contexto
    viejo = repo.anadir_hecho(USER, entidad, atributo, "2,2 bar")
    antes = _filas(repo)

    # El INSERT del nuevo falla (atributo inexistente: FK). El viejo tiene que seguir vigente.
    with pytest.raises(Exception):
        repo.sustituir_hecho(USER, viejo, entidad, 999_999_999, "2,4 bar")

    assert _filas(repo) == antes
    assert repo.hecho(viejo)["valid_to"] is None and repo.hecho(viejo)["superseded_by"] is None
    assert [h["id"] for h in repo.hechos_vigentes(USER, entidad, atributo)] == [viejo]


def test_nada_se_borra(contexto):
    repo, entidad, atributo = contexto
    a = repo.anadir_hecho(USER, entidad, atributo, "uno")
    b = repo.sustituir_hecho(USER, a, entidad, atributo, "dos")
    assert _filas(repo) == 2
    repo.retirar_hecho(b)
    assert _filas(repo) == 2
    assert repo.hechos_vigentes(USER, entidad, atributo) == []
    assert repo.hecho(b)["valid_to"] is not None


def test_historial_incluye_los_cerrados(contexto):
    repo, entidad, atributo = contexto
    a = repo.anadir_hecho(USER, entidad, atributo, "uno")
    b = repo.sustituir_hecho(USER, a, entidad, atributo, "dos")
    historial = repo.hechos_historial(USER, entidad, atributo)
    assert [h["id"] for h in historial] == [a, b]


def test_registrar_decision_guarda_senales_como_json(contexto):
    repo, entidad, atributo = contexto
    did = repo.registrar_decision(USER, "sustituir", {"via": "alias", "fuerte": True},
                                  "entidad=1 atributo=2 regla=uno_distinto_fuerte", hecho_id=None)
    filas = repo.decisiones(USER)
    assert [f["id"] for f in filas] == [did]
    assert filas[0]["tipo"] == "sustituir" and filas[0]["senales"]["via"] == "alias"


def test_alias_y_catalogo_para_el_extractor(contexto):
    repo, entidad, _ = contexto
    repo.anadir_alias_entidad(entidad, "el cochecito")
    assert "cochecito" in repo.alias_de_entidades(USER)[entidad]
    alias = repo.alias_de_atributos()
    nombres = {a["nombre"]: a["id"] for a in repo.listar_atributos()}
    assert "alergias" in alias[nombres["alergia"]]
