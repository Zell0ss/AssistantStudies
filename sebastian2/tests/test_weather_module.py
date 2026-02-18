# tests/test_weather_module.py
import pytest
from modules.user_settings import UserSettingsModule
from db.connection import get_connection, close_connection

TEST_USER = "test_user_weather"

@pytest.fixture
def db_conn():
    conn = get_connection()
    yield conn
    close_connection()

@pytest.fixture
def settings(db_conn):
    s = UserSettingsModule(db_conn, TEST_USER)
    yield s
    cursor = db_conn.cursor()
    cursor.execute("DELETE FROM user_settings WHERE user_id = %s", (TEST_USER,))
    db_conn.commit()


class TestWeatherLocation:
    def test_get_weather_location_returns_default_madrid(self, settings):
        loc = settings.get_weather_location()
        assert loc['location'] == 'Madrid'
        assert abs(loc['lat'] - 40.4168) < 0.001
        assert abs(loc['lon'] - -3.7038) < 0.001
        assert loc['country'] == 'ES'

    def test_set_weather_location_persists(self, settings, db_conn):
        settings.set_weather_location('Gijón', 43.5453, -5.6615, 'ES')
        loc = settings.get_weather_location()
        assert loc['location'] == 'Gijón'
        assert abs(loc['lat'] - 43.5453) < 0.001

    def test_set_weather_location_returns_dict(self, settings):
        result = settings.set_weather_location('Oviedo', 43.3619, -5.8494, 'ES')
        assert result['success'] is True
        assert 'Oviedo' in result['message']


from unittest.mock import patch, MagicMock
from modules.weather import WeatherModule

# Reusable mock forecast API response
MOCK_FORECAST = {
    "current": {"time": "2026-02-18T10:00", "temperature_2m": 8.5, "precipitation": 0.0},
    "daily": {
        "temperature_2m_max": [14.2],
        "temperature_2m_min": [4.8],
        "sunrise": ["2026-02-18T07:45"],
        "sunset":  ["2026-02-18T18:32"],
        "precipitation_probability_max": [20],
    }
}

MOCK_GEOCODING = {
    "results": [{
        "name": "Magán",
        "latitude": 39.9977,
        "longitude": -3.7817,
        "country_code": "ES",
        "admin1": "Castilla-La Mancha"
    }]
}


class TestWeatherModule:
    def test_get_weather_uses_saved_location_when_no_city(self, settings, db_conn):
        """No city arg → uses Madrid default from user_settings."""
        with patch('modules.weather._forecast_cache') as mock_cache:
            mock_resp = MagicMock()
            mock_resp.json.return_value = MOCK_FORECAST
            mock_resp.raise_for_status = MagicMock()
            mock_cache.get.return_value = mock_resp

            w = WeatherModule(db_conn, TEST_USER)
            result = w.get_weather(None)

        assert result['success'] is True
        assert '📍' in result['result']
        assert 'Madrid' in result['result']
        assert '8' in result['result']  # current temp

    def test_get_weather_fallback_city(self, settings, db_conn):
        """Known city from fallback list — no geocoding API call needed."""
        with patch('modules.weather._forecast_cache') as mock_cache:
            mock_resp = MagicMock()
            mock_resp.json.return_value = MOCK_FORECAST
            mock_resp.raise_for_status = MagicMock()
            mock_cache.get.return_value = mock_resp

            w = WeatherModule(db_conn, TEST_USER)
            result = w.get_weather('Gijón')

        assert result['success'] is True
        assert 'Gijón' in result['result']

    def test_get_weather_geocodes_unknown_city(self, settings, db_conn):
        """Unknown city → geocoding API called, location saved."""
        with patch('modules.weather._forecast_cache') as mock_cache, \
             patch('modules.weather.requests.get') as mock_geo:

            mock_resp = MagicMock()
            mock_resp.json.return_value = MOCK_FORECAST
            mock_resp.raise_for_status = MagicMock()
            mock_cache.get.return_value = mock_resp

            mock_geo.return_value.json.return_value = MOCK_GEOCODING
            mock_geo.return_value.raise_for_status = MagicMock()

            w = WeatherModule(db_conn, TEST_USER)
            result = w.get_weather('Magán')

        assert result['success'] is True
        assert '📌' in result['result']  # location updated notice
        assert 'Magán' in result['result']
        # Verify saved to DB
        loc = settings.get_weather_location()
        assert loc['location'] == 'Magán'

    def test_get_weather_geocoding_fails_returns_error(self, settings, db_conn):
        """Geocoding API returns no results → graceful error."""
        with patch('modules.weather._forecast_cache'), \
             patch('modules.weather.requests.get') as mock_geo:

            mock_geo.return_value.json.return_value = {}  # no 'results' key
            mock_geo.return_value.raise_for_status = MagicMock()

            w = WeatherModule(db_conn, TEST_USER)
            result = w.get_weather('CiudadInventada')

        assert result['success'] is False
        assert 'CiudadInventada' in result['result']

    def test_get_weather_forecast_api_error(self, settings, db_conn):
        """Forecast API raises → graceful error with message."""
        with patch('modules.weather._forecast_cache') as mock_cache:
            mock_cache.get.side_effect = Exception("network error")

            w = WeatherModule(db_conn, TEST_USER)
            result = w.get_weather(None)

        assert result['success'] is False
        assert 'tiempo' in result['result'].lower()

    def test_response_contains_all_expected_fields(self, settings, db_conn):
        """Response format has emoji sections: location, temp, rain/sun, refran."""
        with patch('modules.weather._forecast_cache') as mock_cache:
            mock_resp = MagicMock()
            mock_resp.json.return_value = MOCK_FORECAST
            mock_resp.raise_for_status = MagicMock()
            mock_cache.get.return_value = mock_resp

            w = WeatherModule(db_conn, TEST_USER)
            result = w.get_weather(None)

        text = result['result']
        assert '📍' in text   # location line
        assert '🌡️' in text   # temperature line
        assert '🌧️' in text   # rain/sun line
        assert '🍷' in text   # refran
