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
        "windspeed_10m_max": [20.0],
        "windgusts_10m_max": [30.0],
        "weathercode": [1],
        "precipitation_sum": [0.0],
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


class TestFallbackCities:
    """Test that ambiguous Spanish cities resolve correctly without geocoding."""

    def setup_method(self):
        with patch('modules.weather.UserSettingsModule'):
            self.module = WeatherModule(None, "test_user_fallback")

    def _make_mock_settings(self):
        mock_settings = MagicMock()
        mock_settings.get_weather_location.return_value = {
            'location': '', 'lat': 0.0, 'lon': 0.0, 'country': ''
        }
        return mock_settings

    def _make_mock_forecast(self, temp=10):
        mock_forecast = MagicMock()
        mock_forecast.return_value = {
            'temp': temp, 'precip': 0, 'temp_max': temp + 5, 'temp_min': temp - 5,
            'sunrise': '07:30', 'sunset': '18:00', 'precip_prob': 20,
            'windgusts': 20, 'windspeed': 15,
        }
        return mock_forecast

    def test_salamanca_resolves_to_spain(self):
        mock_settings = self._make_mock_settings()
        self.module._settings = mock_settings
        with patch.object(self.module, '_fetch_forecast', return_value={
            'temp': 10, 'precip': 0, 'temp_max': 15, 'temp_min': 5,
            'sunrise': '07:30', 'sunset': '18:00', 'precip_prob': 20,
            'windgusts': 20, 'windspeed': 15,
        }):
            self.module.get_weather('Salamanca')
        call_args = mock_settings.set_weather_location.call_args
        _, lat, lon, country = call_args[0]
        assert country == 'ES', f"Expected ES, got {country}"
        assert 40.0 < lat < 41.5, f"Lat {lat} outside Salamanca ES range"

    def test_leon_resolves_to_spain(self):
        mock_settings = self._make_mock_settings()
        self.module._settings = mock_settings
        with patch.object(self.module, '_fetch_forecast', return_value={
            'temp': 8, 'precip': 0, 'temp_max': 12, 'temp_min': 3,
            'sunrise': '08:00', 'sunset': '18:30', 'precip_prob': 10,
            'windgusts': 15, 'windspeed': 10,
        }):
            self.module.get_weather('León')
        call_args = mock_settings.set_weather_location.call_args
        _, lat, lon, country = call_args[0]
        assert country == 'ES', f"Expected ES, got {country}"

    def test_vitoria_resolves_to_spain(self):
        mock_settings = self._make_mock_settings()
        self.module._settings = mock_settings
        with patch.object(self.module, '_fetch_forecast', return_value={
            'temp': 9, 'precip': 0, 'temp_max': 13, 'temp_min': 4,
            'sunrise': '07:45', 'sunset': '18:15', 'precip_prob': 15,
            'windgusts': 18, 'windspeed': 12,
        }):
            self.module.get_weather('Vitoria')
        call_args = mock_settings.set_weather_location.call_args
        _, lat, lon, country = call_args[0]
        assert country == 'ES', f"Expected ES, got {country}"


class TestGeocoding:
    """Test geocoding prefers Spanish results when available."""

    def setup_method(self):
        with patch('modules.weather.UserSettingsModule'):
            self.module = WeatherModule(None, "test_user_geo")

    @patch('modules.weather.requests.get')
    def test_prefers_spanish_result_over_latin_american(self, mock_get):
        # Simulate OpenMeteo returning Mexico first, then Spain
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            'results': [
                {'name': 'Salamanca', 'latitude': 22.0, 'longitude': -101.0, 'country_code': 'MX'},
                {'name': 'Salamanca', 'latitude': 40.97, 'longitude': -5.66, 'country_code': 'ES'},
            ]
        }
        result = self.module._geocode('Salamanca')
        assert result['country'] == 'ES'
        assert abs(result['lat'] - 40.97) < 0.1

    @patch('modules.weather.requests.get')
    def test_falls_back_to_first_when_no_es(self, mock_get):
        # No Spanish result — return first (existing behavior)
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            'results': [
                {'name': 'Miami', 'latitude': 25.77, 'longitude': -80.19, 'country_code': 'US'},
                {'name': 'Miami', 'latitude': 26.0, 'longitude': -80.5, 'country_code': 'US'},
            ]
        }
        result = self.module._geocode('Miami')
        assert result['country'] == 'US'
        assert abs(result['lat'] - 25.77) < 0.1

    @patch('modules.weather.requests.get')
    def test_geocode_requests_count_5(self, mock_get):
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {'results': []}
        self.module._geocode('Test')
        call_kwargs = mock_get.call_args[1]['params']
        assert call_kwargs['count'] == 5


class TestUmbrellaAdvice:
    """_build_advice returns appropriate warnings."""

    def setup_method(self):
        with patch('modules.weather.UserSettingsModule'):
            self.module = WeatherModule(None, "test_user_advice")

    def test_umbrella_warning_when_rain_likely(self):
        forecast = {'precip_prob': 65, 'windgusts': 20}
        advice = self.module._build_advice(forecast)
        assert '☂️' in advice

    def test_no_umbrella_when_dry(self):
        forecast = {'precip_prob': 30, 'windgusts': 20}
        advice = self.module._build_advice(forecast)
        assert '☂️' not in advice

    def test_wind_warning_when_gale(self):
        forecast = {'precip_prob': 10, 'windgusts': 65}
        advice = self.module._build_advice(forecast)
        assert '🌬️' in advice

    def test_severe_wind_warning(self):
        forecast = {'precip_prob': 10, 'windgusts': 80}
        advice = self.module._build_advice(forecast)
        assert '🌪️' in advice

    def test_no_wind_warning_when_calm(self):
        forecast = {'precip_prob': 10, 'windgusts': 40}
        advice = self.module._build_advice(forecast)
        assert '🌬️' not in advice
        assert '🌪️' not in advice

    def test_both_warnings_combined(self):
        forecast = {'precip_prob': 70, 'windgusts': 75}
        advice = self.module._build_advice(forecast)
        assert '☂️' in advice
        assert '🌪️' in advice

    def test_empty_advice_when_fine(self):
        forecast = {'precip_prob': 20, 'windgusts': 25}
        advice = self.module._build_advice(forecast)
        assert advice == ''


class TestForecastWindData:
    """Forecast dict includes wind data."""

    @patch('modules.weather._forecast_cache')
    def test_forecast_includes_wind(self, mock_cache):
        mock_cache.get.return_value.raise_for_status = MagicMock()
        mock_cache.get.return_value.json.return_value = {
            'current': {'temperature_2m': 12, 'precipitation': 0},
            'daily': {
                'temperature_2m_max': [15], 'temperature_2m_min': [8],
                'sunrise': ['2026-02-23T07:30'], 'sunset': ['2026-02-23T18:00'],
                'precipitation_probability_max': [30],
                'windspeed_10m_max': [25.0],
                'windgusts_10m_max': [45.0],
                'weathercode': [2],
                'precipitation_sum': [0.0],
            }
        }
        with patch('modules.weather.UserSettingsModule'):
            module = WeatherModule(None, "test_user_wind")
        result = module._fetch_forecast(40.4, -3.7)
        assert 'windgusts' in result
        assert result['windgusts'] == 45.0
        assert 'windspeed' in result
        assert result['windspeed'] == 25.0
        assert 'weathercode' in result
        assert result['weathercode'] == 2
