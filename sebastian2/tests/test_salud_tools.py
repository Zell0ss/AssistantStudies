"""Descripción de la tool `salud` (D46, fase 3): cubre sueño, comidas, hambre y saciedad, y deja
fuera lo que se confunde con ellas. El comportamiento real lo validan los goldens #24-43."""

from core.tools.salud_tools import FAMILY_SUMMARY, SALUD_TOOLS


def _descripcion() -> str:
    return SALUD_TOOLS[0]["description"]


def test_la_descripcion_cubre_sueno_comida_hambre_y_saciedad():
    d = _descripcion().lower()
    for palabra in ("dormido", "comido", "picoteado", "hambre", "lleno"):
        assert palabra in d


def test_la_descripcion_excluye_recordatorios_compra_y_recetas():
    d = _descripcion().lower()
    assert "recuérdame" in d and "compra" in d and "receta" in d


def test_el_parametro_sigue_siendo_mensaje():
    esquema = SALUD_TOOLS[0]["input_schema"]
    assert list(esquema["properties"]) == ["mensaje"] and esquema["required"] == ["mensaje"]


def test_el_resumen_de_familia_habla_de_comidas():
    assert "comido" in FAMILY_SUMMARY and "hambre" in FAMILY_SUMMARY
