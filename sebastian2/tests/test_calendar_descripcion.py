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


# --- Fase 3 H3b (R2, R3, R4, R5): mover por id, crear sin duplicar, el año y un intervalo es un compromiso. Sin API. ---

def _tool(nombre):
    return next(t for t in ALL_TOOLS if t["name"] == nombre)


def _plano(texto):
    return " ".join(texto.split())


def test_update_event_admite_event_id_y_manda_buscar_antes():
    t = _tool("calendar_update_event")
    props = t["input_schema"]["properties"]
    assert props["event_id"]["type"] == "integer"
    assert "title" not in t["input_schema"].get("required", [])          # el id basta
    d = _plano(t["description"])
    assert "calendar_search_events" in d and "`event_id`" in d
    assert "no lo crees de nuevo" in d.lower() or "no lo crees" in d.lower()


def test_update_event_dice_que_mes_y_ano_toma_si_solo_dan_el_dia():
    d = _plano(_tool("calendar_update_event")["input_schema"]["properties"]["new_date"]["description"])
    assert "al 29" in d and "mes y el año" in d and "fecha actual del evento" in d


def test_add_event_manda_buscar_antes_y_usar_el_existente():
    d = _plano(_tool("calendar_add_event")["description"])
    assert "Busca antes si la cita ya existe" in d and "calendar_search_events" in d
    assert "exists" in d and "usa ese evento" in d.lower()


def test_add_event_dice_que_ano_toma_si_solo_dan_dia_y_mes():
    d = _plano(_tool("calendar_add_event")["input_schema"]["properties"]["date"]["description"])
    assert "año" in d.lower() and "fecha de hoy" in d.lower()


def test_compromisos_crear_un_intervalo_es_un_solo_compromiso():
    d = _plano(_tool("compromisos_crear")["description"])
    assert "un solo compromiso" in d and "dias_inicio" in d and "dias_fin" in d


def test_salud_sin_palabras_pegadas():
    d = _tool("salud")["description"]
    assert "ahora.Varias" not in d and "llama a" + "esa" not in d
    assert "ahora. Varias" in d and "llama también a esa tool" in d
    assert len(d) <= 500                                                 # el tope de test_salud_tools


def test_alfred_no_ofrece_guardar_resultados_medicos():
    from core.orchestrator import _ALFRED_SYSTEM
    t = _plano(_ALFRED_SYSTEM)
    assert ("Si el usuario cuenta un resultado o un diagnóstico médico, no ofrezcas guardarlo: "
            "Sebastian no los guarda") in t


# --- Fase 3 H3c (R8, R9): apuntar a una cita en una sola llamada, y buscar no termina el turno. Sin API. ---

def test_add_note_se_puede_hacer_con_titulo_y_dia_sin_buscar_antes():
    t = _tool("calendar_add_note")
    props = t["input_schema"]["properties"]
    assert {"event_id", "title", "date", "note_text"} <= set(props) and props["event_id"]["type"] == "integer"
    assert t["input_schema"]["required"] == ["note_text"]                 # el id ya no es obligatorio
    d = _plano(t["description"])
    assert "`title` y `date`" in d and "sin buscar antes" in d and "no lo crees de nuevo" in d
    assert "Nunca** resultados ni diagnósticos".replace("**", "") in d.replace("**", "")   # D52 sigue ahí


def test_el_planner_dice_que_buscar_no_termina_el_turno():
    """R9: la forma que ya funcionó en D43 (la regla, al final, justo antes de decidir)."""
    from core.orchestrator import _planner_system
    p = _plano(_planner_system())
    frase = ("Buscar no termina el turno. Si el usuario pidió cambiar algo (una cita, su nota, un compromiso) y la "
             "búsqueda lo encontró, llama en este mismo turno a la tool que lo cambia")
    assert p.rstrip().endswith(frase + ".")                                   # al final, no en medio
