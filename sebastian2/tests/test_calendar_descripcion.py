"""H4 (R16, H4-revision §2.2): la descripción de `calendar_add_event` dice qué hacer cuando falta la hora, en vez de dejar que
el modelo la invente (golden #28: «recuérdame acostarme pronto» acabó como un evento real a las 23:00). Sin API."""
from core.tools import ALL_TOOLS


def _descripcion():
    return next(t for t in ALL_TOOLS if t["name"] == "calendar_add_event")["description"]


def test_no_inventa_dia_ni_hora_y_pregunta():
    d = " ".join(_descripcion().split())
    assert "Si el usuario no da día y hora, no te los inventes: pregunta con `request_clarification`" in d
    assert 'Un recordatorio sin hora ("recuérdame acostarme pronto") no es un evento' in d


def test_sigue_valiendo_para_citas_y_eventos():
    d = _descripcion().lower()
    assert "crea un nuevo evento" in d and "cita" in d


def test_request_clarification_existe_como_tool():
    assert any(t["name"] == "request_clarification" for t in ALL_TOOLS)


def test_el_golden_28_admite_ninguna_nota_o_aclaracion_y_cita_el_cambio():
    import yaml
    from pathlib import Path
    ruta = Path(__file__).parent / "golden" / "goldens.yaml"
    g = next(x for x in yaml.safe_load(ruta.read_text(encoding="utf-8")) if x["id"] == 28)
    assert g["mode"] == "any_of" and g["expected"] == [[], ["notes_create"], ["request_clarification"]]
    texto = ruta.read_text(encoding="utf-8")
    # El comentario que cita el cambio (del arquitecto, H4-revision) está justo encima del golden, sin otro golden por medio.
    cita = texto.index("H4-revision §2.2")
    assert "arquitecto" in texto[cita - 80:cita + 40] and "- id:" not in texto[cita:texto.index("- id: 28")]
