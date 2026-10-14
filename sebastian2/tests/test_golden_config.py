"""H4 §5 (D27): la config de los goldens no apunta a ningún servicio real con escritura. Sin API."""
import inspect
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import pytest

from core.tool_executor import ToolExecutor
from tests.golden import conftest as conftest_goldens
from tests.golden.aislamiento import neutralizar_servicios_externos
from utils.config import get_config


@pytest.fixture
def config_goldens(tmp_path):
    # Misma función que usa la fixture `config_de_goldens` del harness, partiendo del config.yaml real.
    return neutralizar_servicios_externos(dict(get_config()), tmp_path)


def test_goldens_no_apuntan_a_tristras_real(config_goldens):
    url = urlparse(config_goldens["tristras_url"])
    assert ":8003" not in config_goldens["tristras_url"]
    assert url.port == 9


def test_goldens_no_llevan_token_real(config_goldens):
    assert config_goldens["tristras_token"] != get_config()["tristras_token"]
    assert config_goldens["tristras_token"] == "golden-sin-tristras"


def test_goldens_no_escriben_en_el_vault(config_goldens):
    # La ruta real que usaría el ejecutor, no la clave: se despacha la tool con `extraer` simulado.
    with patch("core.tool_executor.extraer") as extraer:
        extraer.return_value = {"titulo": "t", "idioma": "es", "subtitulos": "manual",
                                "ruta_md": "x.md", "palabras": 1, "id": "x"}
        ToolExecutor(MagicMock(), "golden", config=config_goldens).execute(
            "youtube_transcript", {"url": "u", "idioma": "es"}
        )
    clippings = Path(extraer.call_args[0][3]).resolve()
    assert not clippings.is_relative_to(Path("/data/library/mi-wiki").resolve())


def test_goldens_youtube_workdir_temporal(config_goldens):
    workdir = Path(config_goldens["youtube_workdir"]).resolve()
    assert workdir.is_relative_to(Path(tempfile.gettempdir()).resolve())
    assert workdir != Path("/data/ytb-video-extracts")


def test_el_harness_usa_la_neutralizacion():
    # Si alguien deja de llamarla en la fixture del harness, los cuatro tests de arriba seguirían
    # en verde sin proteger nada.
    assert "neutralizar_servicios_externos(" in inspect.getsource(conftest_goldens)
