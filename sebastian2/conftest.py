"""H6-encargo.md #1: cada módulo llama a `get_logger("sebastian")` sin `log_dir` (patrón de
`modules/base.py`), así que `logcentral_client` cae en `LOGCENTRAL_LOG_DIR` o, si no está, en
`logs/` relativo al cwd. Puesto aquí, en la raíz, pytest lo carga antes de importar ningún test
ni módulo de la app, así que ninguna suite (incluida `-m golden`) escribe en `logs/` del repo.
"""

import os
import tempfile

_directorio_logs_test = tempfile.TemporaryDirectory(prefix="sebastian-test-logs-")
os.environ["LOGCENTRAL_LOG_DIR"] = _directorio_logs_test.name
