"""H1 (fase 2, plan §3 H1.3): crear_colecciones.py se niega a tocar una base que no sea _test/_dev."""
from scripts.memoria.crear_colecciones import crear_colecciones, main
from tests.fakes_memoria import DIMENSION, QdrantQueDejaMarca, qdrant_en_memoria


def test_crear_colecciones_rechaza_produccion():
    cliente = QdrantQueDejaMarca()

    codigo = main([], base="sebastian_memory", cliente=cliente)

    assert codigo != 0
    assert cliente.llamadas == [], "llego a llamar a Qdrant con una base de produccion"


def test_crear_colecciones_con_flag_produccion_si_crea():
    cliente = QdrantQueDejaMarca()

    codigo = main(["--produccion"], base="sebastian_memory", cliente=cliente)

    assert codigo == 0
    assert cliente.llamadas, "con --produccion tenia que crear las colecciones"


def test_crear_colecciones_test_crea_las_dos_e_idempotente():
    cliente = qdrant_en_memoria()

    assert main([], base="sebastian_memory_test", cliente=cliente) == 0
    assert main([], base="sebastian_memory_test", cliente=cliente) == 0  # repetir no falla

    nombres = {c.name for c in cliente.get_collections().collections}
    assert nombres == {"sebastian_memory_test_catalogo", "sebastian_memory_test_notas"}
    info = cliente.get_collection("sebastian_memory_test_catalogo").config.params.vectors
    assert info.size == DIMENSION
    assert info.distance.name == "COSINE"


def test_crear_colecciones_acepta_dev():
    assert main([], base="sebastian_memory_dev", cliente=qdrant_en_memoria()) == 0
    assert crear_colecciones  # la funcion publica existe
