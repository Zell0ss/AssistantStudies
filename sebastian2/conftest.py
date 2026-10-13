"""H6-encargo.md #1: cada módulo llama a `get_logger("sebastian")` sin `log_dir` (patrón de
`modules/base.py`), así que `logcentral_client` cae en `LOGCENTRAL_LOG_DIR` o, si no está, en
`logs/` relativo al cwd. Puesto aquí, en la raíz, pytest lo carga antes de importar ningún test
ni módulo de la app, así que ninguna suite (incluida `-m golden`) escribe en `logs/` del repo.
"""

import os
import tempfile

_directorio_logs_test = tempfile.TemporaryDirectory(prefix="sebastian-test-logs-")
os.environ["LOGCENTRAL_LOG_DIR"] = _directorio_logs_test.name

# D19/D20/D25: los tests nunca tocan producción. El entorno se fija aquí, antes de importar la
# app, porque utils.config lo lee al cargar el YAML (get_config es un singleton).
os.environ["SEBASTIAN_DB_NAME"] = "sebastian_test"
os.environ["SEBASTIAN_MEMORY_COLLECTION"] = "sebastian_memory_test"

import pytest


@pytest.fixture(scope="session", autouse=True)
def _guardarrail_bd_de_test():
    """Aborta la sesión entera si la conexión de la app no apunta a sebastian_test (D25)."""
    from db.connection import close_connection, get_connection

    cursor = get_connection().cursor()
    cursor.execute("SELECT DATABASE() AS db")
    actual = cursor.fetchone()["db"]
    cursor.close()
    close_connection()
    if actual != "sebastian_test":
        pytest.exit(
            f"ABORTO: la conexión de la app apunta a '{actual}', no a 'sebastian_test'. "
            "Los tests borran filas; no se ejecutan contra otra BD.",
            returncode=1,
        )
    yield
