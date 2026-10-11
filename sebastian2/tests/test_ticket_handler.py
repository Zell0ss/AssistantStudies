# tests/test_ticket_handler.py
"""_intentar_salud — clasificación de fotos sin QR hacia Tristras (D40). handle_media en sí
no tenía harness antes de esto (requeriría mockear bot/Telegram + CalendarModule + DB); este
test cubre solo la pieza nueva, aislada."""
from unittest.mock import MagicMock, patch

from bot.ticket_handler import _intentar_salud

CONFIG = {'tristras_url': 'http://127.0.0.1:8003', 'tristras_token': 'tok'}


@patch('utils.config.get_config', return_value=CONFIG)
@patch('modules.salud.SaludModule.registrar_captura')
def test_sueno_reconocido_devuelve_el_resumen(mock_registrar, mock_config):
    mock_registrar.return_value = {"tipo": "sueno", "registro": {"minutos": 405}, "resumen": "Anoche: 6 h 45 min. Apuntado."}
    assert _intentar_salud(b"\xff\xd8\xff") == "Anoche: 6 h 45 min. Apuntado."


@patch('utils.config.get_config', return_value=CONFIG)
@patch('modules.salud.SaludModule.registrar_captura')
def test_desconocida_devuelve_none(mock_registrar, mock_config):
    """D40: "desconocida" deja que el llamador use su respuesta de siempre."""
    mock_registrar.return_value = {"tipo": "desconocida"}
    assert _intentar_salud(b"\xff\xd8\xff") is None


@patch('utils.config.get_config', return_value=CONFIG)
@patch('modules.salud.SaludModule.registrar_captura')
def test_error_422_devuelve_el_detail(mock_registrar, mock_config):
    """H4-revision.md §1.1: un 422 solo puede pasar después de que Tristras haya clasificado
    la foto como sueño (fases que no cuadran, fecha rara) — el detail ya es seguro de mostrar."""
    mock_registrar.return_value = {
        "tipo": "error",
        "status_code": 422,
        "resumen": "Las fases leídas no cuadran con el total dormido.",
    }
    assert _intentar_salud(b"\xff\xd8\xff") == "Las fases leídas no cuadran con el total dormido."


@patch('utils.config.get_config', return_value=CONFIG)
@patch('modules.salud.SaludModule.registrar_captura')
def test_error_503_devuelve_mensaje_neutro(mock_registrar, mock_config):
    """H4-revision.md §1.1: un 503 no dice qué era la foto — no se puede hablar de sueño."""
    mock_registrar.return_value = {
        "tipo": "error",
        "status_code": 503,
        "resumen": "No he podido leerlo ahora; prueba en un rato.",
    }
    assert _intentar_salud(b"\xff\xd8\xff") == "No he podido mirar bien esa foto ahora. Si era de tu sueño o de tu comida, prueba en un rato."


@patch('utils.config.get_config', return_value=CONFIG)
@patch('modules.salud.SaludModule.registrar_captura')
def test_error_de_red_devuelve_mensaje_neutro(mock_registrar, mock_config):
    """Un fallo de red (status_code None) es el mismo caso que un 503: no se sabe qué era
    la foto, así que tampoco se menciona el sueño."""
    mock_registrar.return_value = {
        "tipo": "error",
        "status_code": None,
        "resumen": "No he podido apuntar eso ahora mismo; pruébalo en un rato.",
    }
    assert _intentar_salud(b"\xff\xd8\xff") == "No he podido mirar bien esa foto ahora. Si era de tu sueño o de tu comida, prueba en un rato."


@patch('modules.salud.SaludModule.registrar_captura')
def test_sin_config_no_llama_a_tristras(mock_registrar):
    """H4-revision.md §1.2: sin tristras_url/tristras_token, el flujo de tickets no puede
    romperse — no se llama a Tristras y se cae en la respuesta de siempre del llamador."""
    with patch('utils.config.get_config', return_value={}):
        assert _intentar_salud(b"\xff\xd8\xff") is None
    mock_registrar.assert_not_called()


@patch('utils.config.get_config', return_value=CONFIG)
@patch('modules.salud.SaludModule.registrar_captura')
def test_manda_la_imagen_como_jpeg(mock_registrar, mock_config):
    mock_registrar.return_value = {"tipo": "desconocida"}
    _intentar_salud(b"\xff\xd8\xff\xe0")
    mock_registrar.assert_called_once_with(b"\xff\xd8\xff\xe0", "captura.jpg", "image/jpeg")


@patch('utils.config.get_config', return_value=CONFIG)
@patch('modules.salud.SaludModule.registrar_captura')
def test_comida_reconocida_devuelve_el_resumen(mock_registrar, mock_config):
    """Fase 3 (D46): una foto de plato se trata igual que una de sueño — se reenvía el resumen."""
    mock_registrar.return_value = {
        "tipo": "comida", "registro": {"descripcion": "lentejas"},
        "resumen": "Apuntado: lentejas con chorizo (≈ 850 kcal). Si algo no es, corrígelo en la app.",
    }
    assert _intentar_salud(b"\xff\xd8\xff") == (
        "Apuntado: lentejas con chorizo (≈ 850 kcal). Si algo no es, corrígelo en la app."
    )


@patch('utils.config.get_config', return_value=CONFIG)
@patch('modules.salud.requests.post')
def test_422_de_validacion_de_fastapi_en_la_foto_da_el_mensaje_neutro(mock_post, mock_config):
    """H6-revision.md §2 / traspaso fase 3 §4.6: un 422 cuyo `detail` es una lista (validación de
    FastAPI, no de Tristras) no garantiza que la foto se clasificara: mensaje neutro, sin hablar
    de sueño ni de comida como cosa segura."""
    respuesta = MagicMock()
    respuesta.status_code = 422
    respuesta.json.return_value = {"detail": [{"loc": ["body"], "msg": "field required"}]}
    mock_post.return_value = respuesta
    assert _intentar_salud(b"\xff\xd8\xff") == (
        "No he podido mirar bien esa foto ahora. Si era de tu sueño o de tu comida, prueba en un rato."
    )
