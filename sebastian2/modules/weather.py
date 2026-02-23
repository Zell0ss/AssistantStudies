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
    'salamanca':       (40.9701, -5.6635, 'ES'),
    'león':            (42.5987, -5.5671, 'ES'),
    'leon':            (42.5987, -5.5671, 'ES'),
    'granada':         (37.1773, -3.5986, 'ES'),
    'vitoria':         (42.8467, -2.6716, 'ES'),
    'vitoria-gasteiz': (42.8467, -2.6716, 'ES'),
    'córdoba':         (37.8882, -4.7794, 'ES'),
    'cordoba':         (37.8882, -4.7794, 'ES'),
    'valladolid':      (41.6523, -4.7245, 'ES'),
    'burgos':          (42.3439, -3.6966, 'ES'),
    'murcia':          (37.9834, -1.1299, 'ES'),
    'alicante':        (38.3452, -0.4810, 'ES'),
    'zaragoza':        (41.6561, -0.8773, 'ES'),
    'pamplona':        (42.8169, -1.6432, 'ES'),
    'santander':       (43.4623, -3.8099, 'ES'),
    'logroño':         (42.4650, -2.4456, 'ES'),
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

    _RAIN_THRESHOLD = 50      # precip_prob % to warn about rain
    _WIND_WARN_KMH = 60       # windgusts km/h → moderate wind warning
    _WIND_SEVERE_KMH = 75     # windgusts km/h → severe wind warning

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

    def _prefer_spanish_result(self, results: list) -> dict:
        """Given a list of geocoding results, prefer country_code=ES if present."""
        for r in results:
            if r.get('country_code') == 'ES':
                return r
        return results[0]

    def _geocode(self, city: str) -> Optional[dict]:
        """Call OpenMeteo geocoding API. Fetches top 5 and prefers ES results."""
        try:
            resp = requests.get(
                'https://geocoding-api.open-meteo.com/v1/search',
                params={'name': city, 'count': 5, 'language': 'es', 'format': 'json'},
                timeout=5
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get('results', [])
            if not results:
                return None
            r = self._prefer_spanish_result(results)
            return {
                'name': r['name'],
                'lat': r['latitude'],
                'lon': r['longitude'],
                'country': r.get('country_code', ''),
            }
        except Exception as e:
            logger.warning(f"Geocoding failed for '{city}': {e}")
            return None

    def _fetch_forecast(self, lat: float, lon: float, days: int = 1) -> dict:
        """Fetch forecast from OpenMeteo. days=1 for today only. Cached 1h."""
        resp = _forecast_cache.get(
            'https://api.open-meteo.com/v1/forecast',
            params={
                'latitude': lat,
                'longitude': lon,
                'current': 'temperature_2m,precipitation',
                'daily': (
                    'temperature_2m_max,temperature_2m_min,sunrise,sunset,'
                    'precipitation_probability_max,precipitation_sum,'
                    'windspeed_10m_max,windgusts_10m_max,weathercode'
                ),
                'forecast_days': days,
                'timezone': 'auto',
            }
        )
        resp.raise_for_status()
        data = resp.json()
        current = data['current']
        daily = data['daily']

        if days == 1:
            return {
                'temp': current['temperature_2m'],
                'precip': current['precipitation'],
                'temp_max': daily['temperature_2m_max'][0],
                'temp_min': daily['temperature_2m_min'][0],
                'sunrise': daily['sunrise'][0][-5:],
                'sunset': daily['sunset'][0][-5:],
                'precip_prob': daily['precipitation_probability_max'][0],
                'windspeed': daily['windspeed_10m_max'][0],
                'windgusts': daily['windgusts_10m_max'][0],
                'weathercode': daily['weathercode'][0],
            }
        # Multi-day: return full daily arrays
        return {
            'dates': [s[:10] for s in daily['sunrise']],
            'temp_max': daily['temperature_2m_max'],
            'temp_min': daily['temperature_2m_min'],
            'precip_prob': daily['precipitation_probability_max'],
            'windspeed': daily['windspeed_10m_max'],
            'windgusts': daily['windgusts_10m_max'],
            'weathercode': daily['weathercode'],
        }

    def _build_advice(self, forecast: dict) -> str:
        """Build umbrella/wind advice string. Returns '' if nothing to warn about."""
        lines = []
        precip_prob = forecast.get('precip_prob', 0) or 0
        windgusts = forecast.get('windgusts', 0) or 0

        if precip_prob >= self._RAIN_THRESHOLD:
            lines.append("☂️ Lleve paraguas, señor. Probabilidad alta de lluvia.")

        if windgusts >= self._WIND_SEVERE_KMH:
            lines.append(f"🌪️ Viento severo ({windgusts:.0f} km/h) — evite salir si puede.")
        elif windgusts >= self._WIND_WARN_KMH:
            lines.append(f"🌬️ Ráfagas de {windgusts:.0f} km/h — tome precauciones.")

        return '\n'.join(lines)

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
        advice = self._build_advice(forecast)
        if advice:
            lines.append(advice)
        lines.append(f'🍷 "{refran}"')
        return '\n'.join(lines)
