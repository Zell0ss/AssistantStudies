"""Descripción de la tool `salud` (D46, fase 3): cubre sueño, comidas, hambre y saciedad, y deja
fuera lo que se confunde con ellas. El comportamiento real lo validan los goldens #24-49.

H3-revision §2.1: la descripción es CORTA (la tool más amplia no puede pesar sobre las demás, D3/D46)
y no copia frases de los goldens, o estos dejarían de medir si el planner generaliza."""

from pathlib import Path

import yaml

from core.tools.salud_tools import FAMILY_SUMMARY, SALUD_TOOLS

GOLDENS = yaml.safe_load((Path(__file__).parent / "golden" / "goldens.yaml").read_text())
MAX_CARACTERES = 500


def _descripcion() -> str:
    return SALUD_TOOLS[0]["description"]


def test_la_descripcion_es_corta():
    assert len(_descripcion()) <= MAX_CARACTERES


def test_la_descripcion_no_copia_frases_de_los_goldens():
    d = _descripcion().lower()
    copiadas = [g["id"] for g in GOLDENS if g["phrase"].lower().strip("¿?.! ") in d]
    assert not copiadas, f"la descripción contiene literalmente la frase de los goldens {copiadas}"


def test_la_descripcion_cubre_sueno_comida_hambre_y_saciedad():
    d = _descripcion().lower()
    for palabra in ("dormido", "comido", "picoteado", "hambre", "lleno"):
        assert palabra in d


def test_la_descripcion_excluye_recordatorios_compra_y_recetas():
    d = _descripcion().lower()
    for palabra in ("recordatorios", "compra", "recetas"):
        assert palabra in d


def test_el_parametro_sigue_siendo_mensaje():
    esquema = SALUD_TOOLS[0]["input_schema"]
    assert list(esquema["properties"]) == ["mensaje"] and esquema["required"] == ["mensaje"]


def test_el_resumen_de_familia_habla_de_comidas():
    assert "comido" in FAMILY_SUMMARY and "hambre" in FAMILY_SUMMARY
