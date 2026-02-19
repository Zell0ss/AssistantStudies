# modules/weather.py
"""
Weather module for Sebastian 2.0.

Fetches weather from OpenMeteo API (free, no key).
Per-user location stored in user_settings.
Geocoding: fallback dict first, then OpenMeteo geocoding API.
"""
import random
import os
import requests
import requests_cache
from typing import Optional
from loguru import logger
from modules.user_settings import UserSettingsModule

# 1-hour cache for forecast requests
_forecast_cache = requests_cache.CachedSession(
    '.weather_cache', expire_after=3600, backend='sqlite'
)

# Known cities with coordinates — avoids geocoding API for common locations
_FALLBACK_CITIES = {
    'madrid':    (40.4168, -3.7038, 'ES'),
    'gijón':     (43.5453, -5.6615, 'ES'),
    'gijon':     (43.5453, -5.6615, 'ES'),
    'oviedo':    (43.3619, -5.8494, 'ES'),
    'magán':     (39.9977, -3.7817, 'ES'),
    'magan':     (39.9977, -3.7817, 'ES'),
    'toledo':    (39.8628, -4.0273, 'ES'),
    'sevilla':   (37.3882, -5.9823, 'ES'),
    'barcelona': (41.3888,  2.1590, 'ES'),
    'valencia':  (39.4700, -0.3763, 'ES'),
    'bilbao':    (43.2630, -2.9350, 'ES'),
}

_REFRANES_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'refranes.txt')


def _load_refranes() -> list:
    try:
        with open(_REFRANES_PATH, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return ["En abril, aguas mil."]


_REFRANES = _load_refranes()


class WeatherModule:
    """Fetches weather for the user's saved location or an explicit city."""

    def __init__(self, conn, user_id: str):
        self.conn = conn
        self.user_id = user_id
        self._settings = UserSettingsModule(conn, user_id)

    def get_weather(self, city: Optional[str]) -> dict:
        """
        Get weather for city or user's saved location.

        If city is provided and differs from saved location, geocode it
        and save as the new default.

        Returns:
            {success: bool, result: str, data: dict}
        """
        location_updated = False

        if city:
            key = city.lower().strip()
            if key in _FALLBACK_CITIES:
                lat, lon, country = _FALLBACK_CITIES[key]
                display_name = city.title()
                current = self._settings.get_weather_location()
                if current['location'].lower() != key:
                    self._settings.set_weather_location(display_name, lat, lon, country)
                    location_updated = True
            else:
                geo = self._geocode(city)
                if not geo:
                    return {
                        'success': False,
                        'result': f"No encontré la ciudad '{city}'. Prueba con un nombre más completo.",
                        'data': {}
                    }
                display_name = geo['name']
                lat, lon, country = geo['lat'], geo['lon'], geo['country']
                self._settings.set_weather_location(display_name, lat, lon, country)
                location_updated = True
        else:
            saved = self._settings.get_weather_location()
            display_name = saved['location']
            lat, lon, country = saved['lat'], saved['lon'], saved['country']

        try:
            forecast = self._fetch_forecast(lat, lon)
        except Exception as e:
            logger.error(f"Forecast fetch failed: {e}")
            return {
                'success': False,
                'result': "No pude obtener el tiempo ahora mismo. Inténtalo en un momento.",
                'data': {}
            }

        result_text = self._format_response(display_name, country, forecast, location_updated)
        return {
            'success': True,
            'result': result_text,
            'data': forecast
        }

    def get_location(self) -> dict:
        """Return user's saved weather location."""
        return self._settings.get_weather_location()

    def _geocode(self, city: str) -> Optional[dict]:
        """Call OpenMeteo geocoding API. Returns dict or None if not found."""
        try:
            resp = requests.get(
                'https://geocoding-api.open-meteo.com/v1/search',
                params={'name': city, 'count': 1, 'language': 'es', 'format': 'json'},
                timeout=5
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get('results', [])
            if not results:
                return None
            r = results[0]
            return {
                'name': r['name'],
                'lat': r['latitude'],
                'lon': r['longitude'],
                'country': r.get('country_code', ''),
            }
        except Exception as e:
            logger.warning(f"Geocoding failed for '{city}': {e}")
            return None

    def _fetch_forecast(self, lat: float, lon: float) -> dict:
        """Fetch today's forecast from OpenMeteo. Cached 1h."""
        resp = _forecast_cache.get(
            'https://api.open-meteo.com/v1/forecast',
            params={
                'latitude': lat,
                'longitude': lon,
                'current': 'temperature_2m,precipitation',
                'daily': 'temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max',
                'forecast_days': 1,
                'timezone': 'auto',
            }
        )
        resp.raise_for_status()
        data = resp.json()
        current = data['current']
        daily = data['daily']
        return {
            'temp': current['temperature_2m'],
            'precip': current['precipitation'],
            'temp_max': daily['temperature_2m_max'][0],
            'temp_min': daily['temperature_2m_min'][0],
            'sunrise': daily['sunrise'][0][-5:],
            'sunset': daily['sunset'][0][-5:],
            'precip_prob': daily['precipitation_probability_max'][0],
        }

    def _format_response(
        self, location: str, country: str, forecast: dict, location_updated: bool
    ) -> str:
        refran = random.choice(_REFRANES)
        lines = []
        if location_updated:
            lines.append(f"📌 Ubicación actualizada a {location}.")
        lines.append(f"📍 {location}, {country}")
        lines.append(f"🌡️ Ahora: {forecast['temp']}°C  |  Hoy: {forecast['temp_min']}° – {forecast['temp_max']}°C")
        lines.append(f"🌧️ Lluvia: {forecast['precip_prob']}%  |  🌅 {forecast['sunrise']} – 🌇 {forecast['sunset']}")
        lines.append(f'🍷 "{refran}"')
        return '\n'.join(lines)
