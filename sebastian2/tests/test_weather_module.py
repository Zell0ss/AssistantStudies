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
