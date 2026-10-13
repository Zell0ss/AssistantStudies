# utils/config.py
"""
Configuration loader with singleton pattern.
"""
import os

import yaml
from logcentral_client import get_logger

logger = get_logger("sebastian")

_config = None

# D19/D20: qué BD y qué colección usa el proceso lo decide el entorno (la unidad systemd, o el
# conftest en los tests), no el YAML. Así un script lanzado a mano con el .env/config de
# desarrollo nunca escribe en producción.
_OVERRIDES_ENTORNO = (
    ("SEBASTIAN_DB_NAME", ("mariadb", "database")),
    ("SEBASTIAN_MEMORY_COLLECTION", ("memory_collection",)),
)


def _aplicar_overrides_entorno(config: dict) -> dict:
    for variable, ruta in _OVERRIDES_ENTORNO:
        valor = os.environ.get(variable)
        if not valor:
            continue
        destino = config
        for clave in ruta[:-1]:
            destino = destino.setdefault(clave, {})
        destino[ruta[-1]] = valor
    return config


def load_config(config_path='config.yaml'):
    """Load configuration from YAML file, with environment overrides (D19, D20)"""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    _aplicar_overrides_entorno(config)
    logger.info(f"Configuration loaded from {config_path}")
    return config

def get_config():
    """Get cached configuration (singleton)"""
    global _config
    if _config is None:
        _config = load_config()
    return _config
