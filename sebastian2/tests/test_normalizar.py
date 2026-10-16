"""H1 (fase 2, plan §2.4): normalizacion de alias."""
import pytest

from core.memoria.normalizar import normalizar


@pytest.mark.parametrize("texto, esperado", [
    ("El Coche", "coche"),
    ("mis alergias", "alergias"),
    ("Cumpleaños", "cumpleaños"),   # H1-revision §2.1: la regla es que la ñ se queda
    ("año", "año"),                # la ñ se queda; el tilde de otras vocales se va
    ("  la   casa  ", "casa"),
    ("el el", "el"),               # solo se quita UN articulo o posesivo inicial
])
def test_normalizar(texto, esperado):
    assert normalizar(texto) == esperado


def test_normalizar_quita_puntuacion_y_dieresis():
    assert normalizar("¿Pingüino, verde?") == "pinguino verde"


def test_normalizar_vacio():
    assert normalizar("   ") == ""
