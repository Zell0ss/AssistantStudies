"""H4 (adición, ver el informe): indexar el catálogo en `<base>_catalogo`. Embedder falso y Qdrant en memoria: sin API.

En producción nadie indexaba los atributos semilla: `crear_colecciones --produccion` solo crea las colecciones vacías, y
sin ellos la resolución semántica de atributos (D35) no encuentra nada y cae a alias exacto y atributos nuevos."""
import pytest

from core.memoria.catalogo import Catalogo
from core.memoria.repositorio import RepositorioMemoria
from db.connection import close_connection, get_connection
from scripts.memoria.crear_colecciones import crear_colecciones
from scripts.memoria.indexar_catalogo import indexar, main
from tests.fakes_memoria import EmbedderFalso, qdrant_en_memoria

USER = "test_indexar_a"
OTRO = "test_indexar_b"
BASE = "idx_test"


def _limpiar(c):
    cur = c.cursor()
    u = (USER, OTRO)
    cur.execute("DELETE FROM mem_entidad_alias WHERE entidad_id IN (SELECT id FROM mem_entidades WHERE user_id IN (%s, %s))", u)
    cur.execute("DELETE FROM mem_entidades WHERE user_id IN (%s, %s)", u)
    c.commit()


@pytest.fixture
def entorno():
    c = get_connection()
    _limpiar(c)
    repo = RepositorioMemoria(c)
    cliente = qdrant_en_memoria()
    crear_colecciones(cliente, BASE)
    embedder = EmbedderFalso()
    yield c, repo, cliente, embedder
    _limpiar(c)
    close_connection()


def _puntos(cliente):
    puntos, _ = cliente.scroll(f"{BASE}_catalogo", limit=500, with_payload=True)
    return puntos


def test_indexa_todos_los_atributos_y_las_entidades_del_usuario(entorno):
    c, repo, cliente, embedder = entorno
    repo.crear_entidad(USER, "Paco", "persona", estado="activo")
    repo.crear_entidad(OTRO, "Marisol", "persona", estado="activo")

    resultado = indexar(c, cliente, embedder, BASE, USER)

    tipos = [p.payload["tipo"] for p in _puntos(cliente)]
    assert tipos.count("atributo") == resultado["atributos"] == len(repo.listar_atributos())
    assert tipos.count("entidad") == resultado["entidades"] == 1
    nombres = {p.payload["nombre"] for p in _puntos(cliente) if p.payload["tipo"] == "entidad"}
    assert nombres == {"Paco"}                                  # solo las del usuario indicado (D33)


def test_es_idempotente(entorno):
    c, repo, cliente, embedder = entorno
    repo.crear_entidad(USER, "Paco", "persona", estado="activo")
    indexar(c, cliente, embedder, BASE, USER)
    n = len(_puntos(cliente))
    indexar(c, cliente, embedder, BASE, USER)
    assert len(_puntos(cliente)) == n                           # ids deterministas: reindexar pisa el mismo punto


def test_solo_escribe_en_el_catalogo_no_en_las_notas(entorno):
    c, repo, cliente, embedder = entorno
    indexar(c, cliente, embedder, BASE, USER)
    notas, _ = cliente.scroll(f"{BASE}_notas", limit=50)
    assert notas == []


def test_con_el_catalogo_indexado_la_resolucion_semantica_encuentra_las_semillas(entorno):
    c, repo, cliente, embedder = entorno
    indexar(c, cliente, embedder, BASE, USER)
    candidatos = Catalogo(repo, embedder, cliente, BASE).buscar_atributos(
        "Sustancia o alimento que a una persona le provoca alergia o intolerancia", k=1)
    assert candidatos and candidatos[0]["nombre"] == "alergia"


def test_main_se_niega_con_base_de_produccion_sin_el_flag(entorno, capsys):
    c, repo, cliente, embedder = entorno
    codigo = main([], base="sebastian_memory", db=c, qdrant=cliente, embedder=embedder, user_id=USER)
    assert codigo == 2 and _puntos(cliente) == [] and embedder.llamadas == []
    assert "--produccion" in capsys.readouterr().err


def test_main_con_el_flag_indexa(entorno):
    c, repo, cliente, embedder = entorno
    crear_colecciones(cliente, "sebastian_memory")
    assert main(["--produccion"], base="sebastian_memory", db=c, qdrant=cliente, embedder=embedder, user_id=USER) == 0
    puntos, _ = cliente.scroll("sebastian_memory_catalogo", limit=500)
    assert len(puntos) >= len(repo.listar_atributos())
