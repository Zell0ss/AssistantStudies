# tests/test_salud_module.py
"""SaludModule — proxy HTTP hacia /api/ingesta/* de Tristras (D39-D42). Sin red: requests
va mockeado."""
from unittest.mock import MagicMock, patch

from modules.salud import SaludModule

BASE_URL = "http://127.0.0.1:8003"
TOKEN = "el-token-de-prueba"


def _mock_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


class TestRegistrarTexto:
    @patch("modules.salud.requests.post")
    def test_manda_bearer_y_texto(self, mock_post):
        mock_post.return_value = _mock_response(200, {"tipo": "sueno", "resumen": "Anoche: 6 h 45 min. Apuntado."})
        modulo = SaludModule(BASE_URL, TOKEN)

        resultado = modulo.registrar_texto("he dormido 6 horas 45, fatal")

        mock_post.assert_called_once_with(
            f"{BASE_URL}/api/ingesta/texto",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"texto": "he dormido 6 horas 45, fatal"},
            timeout=30,
        )
        assert resultado == "Anoche: 6 h 45 min. Apuntado."

    @patch("modules.salud.requests.post")
    def test_no_entendido_devuelve_su_resumen(self, mock_post):
        mock_post.return_value = _mock_response(200, {"tipo": "no_entendido", "resumen": "No he entendido que fuera sobre tu sueño."})
        modulo = SaludModule(BASE_URL, TOKEN)

        assert modulo.registrar_texto("recuérdame acostarme pronto") == "No he entendido que fuera sobre tu sueño."

    @patch("modules.salud.requests.post")
    def test_error_422_reenvia_el_detail_tal_cual(self, mock_post):
        """H2-revision.md: el detail de un 422 es una frase lista para el usuario."""
        mock_post.return_value = _mock_response(422, {"detail": "Las fases leídas no cuadran con el total dormido."})
        modulo = SaludModule(BASE_URL, TOKEN)

        assert modulo.registrar_texto("dormí fatal") == "Las fases leídas no cuadran con el total dormido."

    @patch("modules.salud.requests.post")
    def test_error_503_reenvia_el_detail_tal_cual(self, mock_post):
        mock_post.return_value = _mock_response(503, {"detail": "No he podido leerlo ahora; prueba en un rato."})
        modulo = SaludModule(BASE_URL, TOKEN)

        assert modulo.registrar_texto("dormí bien") == "No he podido leerlo ahora; prueba en un rato."

    @patch("modules.salud.requests.post")
    def test_sin_conexion_da_aviso_claro_sin_traza(self, mock_post):
        import requests
        mock_post.side_effect = requests.ConnectionError("boom")
        modulo = SaludModule(BASE_URL, TOKEN)

        resultado = modulo.registrar_texto("dormí bien")

        assert "boom" not in resultado  # nunca la traza cruda
        assert resultado == "No he podido apuntar tu sueño ahora mismo; pruébalo en un rato."


class TestRegistrarCaptura:
    @patch("modules.salud.requests.post")
    def test_manda_bearer_y_fichero(self, mock_post):
        mock_post.return_value = _mock_response(200, {"tipo": "sueno", "registro": {"minutos": 405}, "resumen": "Anoche: 6 h 45 min. Apuntado."})
        modulo = SaludModule(BASE_URL, TOKEN)

        resultado = modulo.registrar_captura(b"\xff\xd8\xff", "foto.jpg", "image/jpeg")

        assert mock_post.call_args.kwargs["headers"] == {"Authorization": f"Bearer {TOKEN}"}
        assert mock_post.call_args.kwargs["files"] == {"imagen": ("foto.jpg", b"\xff\xd8\xff", "image/jpeg")}
        assert resultado["tipo"] == "sueno"
        assert resultado["resumen"] == "Anoche: 6 h 45 min. Apuntado."

    @patch("modules.salud.requests.post")
    def test_desconocida_no_trae_resumen(self, mock_post):
        """D40: una foto no reconocida no lleva resumen de Tristras — el llamador usa su
        respuesta de siempre, no inventa una."""
        mock_post.return_value = _mock_response(200, {"tipo": "desconocida"})
        modulo = SaludModule(BASE_URL, TOKEN)

        resultado = modulo.registrar_captura(b"\xff\xd8\xff", "foto.jpg", "image/jpeg")

        assert resultado == {"tipo": "desconocida"}

    @patch("modules.salud.requests.post")
    def test_sin_conexion_da_tipo_error(self, mock_post):
        import requests
        mock_post.side_effect = requests.Timeout("boom")
        modulo = SaludModule(BASE_URL, TOKEN)

        resultado = modulo.registrar_captura(b"\xff\xd8\xff", "foto.jpg", "image/jpeg")

        assert resultado["tipo"] == "error"
        assert "boom" not in resultado["resumen"]
