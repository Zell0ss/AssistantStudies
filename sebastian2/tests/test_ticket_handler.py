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
def test_error_de_tristras_devuelve_none(mock_registrar, mock_config):
    """Un fallo de Tristras tampoco debe mostrar un texto de salud para una foto que podría
    no tener nada que ver — cae en la respuesta de siempre, igual que "desconocida"."""
    mock_registrar.return_value = {"tipo": "error", "resumen": "No he podido apuntar tu sueño ahora mismo; pruébalo en un rato."}
    assert _intentar_salud(b"\xff\xd8\xff") is None


@patch('utils.config.get_config', return_value=CONFIG)
@patch('modules.salud.SaludModule.registrar_captura')
def test_manda_la_imagen_como_jpeg(mock_registrar, mock_config):
    mock_registrar.return_value = {"tipo": "desconocida"}
    _intentar_salud(b"\xff\xd8\xff\xe0")
    mock_registrar.assert_called_once_with(b"\xff\xd8\xff\xe0", "captura.jpg", "image/jpeg")
