"""Fase 4, H1j (D74, R25): con historial, las consultas también pasan por `search_memory`. Sin API."""
from core.orchestrator import _REGLA_ACCIONES_CON_HISTORIAL, _planner_system

FRASE = ("Si el usuario pregunta qué consta de él, de su gente, de sus cosas o de sus proyectos («¿qué sabes de…?», «¿qué datos "
         "tienes de…?», «¿cuál es mi…?»), tu respuesta de este turno tiene que ser una llamada a `search_memory`, aunque el "
         "historial parezca tener el dato: lo que se dijo en otro turno no es fuente (D26).")


def test_h1j_la_frase_de_las_consultas_esta_en_el_system_del_planner_despues_de_la_regla_de_acciones():
    system = _planner_system("Lo que me consta de ti:\n- yo (tú): telegram_id, nota")
    assert FRASE in system
    guardar = system.index("Nunca contestes en texto que ya está hecho")
    assert guardar < system.index(FRASE)                                  # después de lo de guardar, en la misma regla
    assert system.index(FRASE) < system.index("Lo que el usuario tiene que HACER")      # y antes de las reglas siguientes (compromisos…)
    assert FRASE in _REGLA_ACCIONES_CON_HISTORIAL                          # forma parte de la misma regla, no de otra


def test_h1j_lo_que_dice_la_regla_sobre_guardar_no_cambia():
    assert _REGLA_ACCIONES_CON_HISTORIAL.startswith(
        "\n\nSi el usuario pide guardar, corregir u olvidar un dato de memoria (algo duradero sobre él, su gente, sus cosas "
        "o sus proyectos), tu respuesta de este turno tiene que ser una llamada a `mark_as_memorable`, aunque el historial "
        "parezca que ya se hizo: el historial es lo que se dijo, no lo que se ha hecho en este turno. Nunca contestes en "
        "texto que ya está hecho: aunque en el historial el asistente diga «Anotado» o «Retirado», eso fue otro turno y no cuenta.")
