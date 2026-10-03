"""H6-encargo.md #1: cada módulo llama a `get_logger("sebastian")` sin `log_dir`, así que cae
en `LOGCENTRAL_LOG_DIR` (ver conftest.py de la raíz, que lo redirige a un directorio temporal
antes de importar nada) o, si no estuviera puesta, en `logs/` relativo al cwd — por eso importa
que la suite nunca llegue a depender de ese fallback."""

import os
from pathlib import Path

from logcentral_client import get_logger

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_logcentral_log_dir_de_tests_no_es_el_del_repo():
    assert os.environ.get("LOGCENTRAL_LOG_DIR") not in (None, "", str(REPO_ROOT / "logs"))


def test_logar_no_crea_logs_en_el_repo():
    get_logger("sebastian").bind(module=__name__).info("prueba H6-encargo #1")
    assert not (REPO_ROOT / "logs").exists()
