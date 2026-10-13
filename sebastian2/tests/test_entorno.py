"""H1 (fase 1): producción y desarrollo separados — D19, D20, D25."""
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

import utils.config as config_module
from core.tool_executor import ToolExecutor
from db.connection import close_connection, get_connection

RAIZ = Path(__file__).resolve().parent.parent


def _yaml_de_prueba(directorio: Path) -> None:
    (directorio / "config.yaml").write_text(
        "mariadb:\n  host: localhost\n  port: 3306\n  user: u\n  password: p\n"
        "  database: sebastian_dev\n"
        "memory_collection: coleccion_del_yaml\n"
    )


def _config_recien_cargada(monkeypatch, directorio: Path) -> dict:
    """Resetea el singleton (monkeypatch lo restaura al salir) y carga el YAML del directorio."""
    _yaml_de_prueba(directorio)
    monkeypatch.chdir(directorio)
    monkeypatch.setattr(config_module, "_config", None)
    return config_module.get_config()


def test_override_db_name_desde_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("SEBASTIAN_DB_NAME", "x")
    config = _config_recien_cargada(monkeypatch, tmp_path)
    assert config["mariadb"]["database"] == "x"


def test_override_memory_collection_desde_entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("SEBASTIAN_MEMORY_COLLECTION", "y")
    config = _config_recien_cargada(monkeypatch, tmp_path)
    assert config["memory_collection"] == "y"


def test_conexion_de_tests_es_sebastian_test():
    close_connection()
    cursor = get_connection().cursor()
    cursor.execute("SELECT DATABASE() AS db")
    assert cursor.fetchone()["db"] == "sebastian_test"
    cursor.close()
    close_connection()


def test_sin_memory_collection_falla():
    executor = ToolExecutor(None, "99999", config={"openai_apikey": "sk-fake"})
    with pytest.raises(KeyError):
        executor._memory_module()


def test_ninguna_migracion_lleva_use():
    migraciones = sorted((RAIZ / "db" / "migrations").glob("*.sql"))
    assert migraciones
    con_use = [m.name for m in migraciones if re.search(r"(?im)^\s*USE\s+", m.read_text())]
    assert con_use == []


def test_setup_db_rechaza_produccion(tmp_path):
    marca = tmp_path / "mysql_ejecutado"
    for nombre in ("mysql", "sudo"):
        falso = tmp_path / nombre
        falso.write_text(f'#!/bin/bash\necho "$0 $@" >> "{marca}"\n')
        falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
    entorno = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}

    resultado = subprocess.run(
        ["bash", "db/setup_db.sh", "sebastian_db"],
        cwd=RAIZ, env=entorno, capture_output=True, text=True,
    )

    assert resultado.returncode != 0
    assert not marca.exists(), "setup_db.sh llegó a invocar mysql/sudo con sebastian_db"
