# Weather Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add per-user weather queries to Sebastian 2.0 using OpenMeteo's free API, with dynamic geocoding and persistent location storage.

**Architecture:** Haiku parser extracts `{module: "weather", action: "get", city: "..."}`. Router calls WeatherModule which geocodes (fallback dict first, then OpenMeteo geocoding API), fetches forecast with 1h cache, and returns a formatted Spanish response with a random refran. The user's location is stored in `user_settings` so subsequent queries without a city use their last location.

**Tech Stack:** OpenMeteo API (free, no key), `requests-cache==1.2.1` (1h forecast cache), `requests` (geocoding, no cache needed), MariaDB via existing `user_settings` table (migration 006 adds columns).

---

### Task 1: Migration 006 + refranes.txt

**Files:**
- Create: `db/migrations/006_weather_location.sql`
- Create: `data/refranes.txt`

**Step 1: Create migration file**

```sql
-- sebastian2/db/migrations/006_weather_location.sql
-- Adds per-user weather location to user_settings

ALTER TABLE user_settings
  ADD COLUMN IF NOT EXISTS weather_location VARCHAR(100) DEFAULT 'Madrid',
  ADD COLUMN IF NOT EXISTS weather_lat      FLOAT        DEFAULT 40.4168,
  ADD COLUMN IF NOT EXISTS weather_lon      FLOAT        DEFAULT -3.7038,
  ADD COLUMN IF NOT EXISTS weather_country  VARCHAR(50)  DEFAULT 'ES';
```

**Step 2: Copy refranes.txt from the old project**

```bash
cp /data/AssistantStudies/data/refranes.txt /data/AssistantStudies/sebastian2/data/refranes.txt
```

Verify: `wc -l sebastian2/data/refranes.txt` → should show 124

**Step 3: Apply migration to dev DB**

```bash
sudo mysql sebastian_db < db/migrations/006_weather_location.sql
sudo mysql sebastian_db -e "DESCRIBE user_settings" | grep weather
```

Expected output (4 rows):
```
weather_location | varchar(100) | YES | | Madrid |
weather_lat      | float        | YES | | 40.4168 |
weather_lon      | float        | YES | | -3.7038 |
weather_country  | varchar(50)  | YES | | ES      |
```

**Step 4: Commit**

```bash
git add db/migrations/006_weather_location.sql data/refranes.txt
git commit -m "feat: add weather location columns and refranes data"
```

---

### Task 2: UserSettingsModule — weather location methods

**Files:**
- Modify: `modules/user_settings.py` (add two methods after `set_sprite_skin`)

**Step 1: Write the failing tests**

Add to `tests/test_weather_module.py` (create the file):

```python
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
```

**Step 2: Run to confirm they fail**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
pytest tests/test_weather_module.py::TestWeatherLocation -v
```

Expected: FAIL — `AttributeError: 'UserSettingsModule' object has no attribute 'get_weather_location'`

**Step 3: Add methods to `modules/user_settings.py`**

Add after the `set_sprite_skin` method (around line 89):

```python
    def get_weather_location(self) -> dict:
        """
        Get user's saved weather location.

        Returns:
            Dict with location, lat, lon, country
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT weather_location, weather_lat, weather_lon, weather_country "
            "FROM user_settings WHERE user_id = %s",
            (self.user_id,)
        )
        result = cursor.fetchone()
        if result:
            return {
                'location': result['weather_location'] or 'Madrid',
                'lat': result['weather_lat'] or 40.4168,
                'lon': result['weather_lon'] or -3.7038,
                'country': result['weather_country'] or 'ES',
            }
        return {'location': 'Madrid', 'lat': 40.4168, 'lon': -3.7038, 'country': 'ES'}

    def set_weather_location(self, location: str, lat: float, lon: float, country: str) -> dict:
        """
        Save user's weather location.

        Args:
            location: City name
            lat: Latitude
            lon: Longitude
            country: Country code (e.g. 'ES')

        Returns:
            Result dict with success and message
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE user_settings
            SET weather_location = %s, weather_lat = %s, weather_lon = %s,
                weather_country = %s, updated_at = NOW()
            WHERE user_id = %s
            """,
            (location, lat, lon, country, self.user_id)
        )
        self.conn.commit()
        logger.info(f"User {self.user_id} weather location set to: {location}")
        return {'success': True, 'message': f'Ubicación del tiempo actualizada a: {location}'}
```

**Step 4: Run tests**

```bash
pytest tests/test_weather_module.py::TestWeatherLocation -v
```

Expected: 3 PASS

**Step 5: Commit**

```bash
git add modules/user_settings.py tests/test_weather_module.py
git commit -m "feat: add weather location methods to UserSettingsModule"
```

---

### Task 3: WeatherModule — core implementation

**Files:**
- Create: `modules/weather.py`

**Step 1: Write failing tests** (add to `tests/test_weather_module.py`)

```python
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
        with patch('modules.weather.requests_cache.CachedSession') as MockSession:
            mock_session = MagicMock()
            MockSession.return_value = mock_session
            mock_session.get.return_value.json.return_value = MOCK_FORECAST
            mock_session.get.return_value.raise_for_status = MagicMock()

            w = WeatherModule(db_conn, TEST_USER)
            result = w.get_weather(None)

        assert result['success'] is True
        assert '📍' in result['result']
        assert 'Madrid' in result['result']
        assert '8' in result['result']  # current temp

    def test_get_weather_fallback_city(self, settings, db_conn):
        """Known city from fallback list — no geocoding API call needed."""
        with patch('modules.weather.requests_cache.CachedSession') as MockSession:
            mock_session = MagicMock()
            MockSession.return_value = mock_session
            mock_session.get.return_value.json.return_value = MOCK_FORECAST
            mock_session.get.return_value.raise_for_status = MagicMock()

            w = WeatherModule(db_conn, TEST_USER)
            result = w.get_weather('Gijón')

        assert result['success'] is True
        assert 'Gijón' in result['result']

    def test_get_weather_geocodes_unknown_city(self, settings, db_conn):
        """Unknown city → geocoding API called, location saved."""
        with patch('modules.weather.requests_cache.CachedSession') as MockSession, \
             patch('modules.weather.requests.get') as mock_geo:

            mock_session = MagicMock()
            MockSession.return_value = mock_session
            mock_session.get.return_value.json.return_value = MOCK_FORECAST
            mock_session.get.return_value.raise_for_status = MagicMock()

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
        with patch('modules.weather.requests_cache.CachedSession'), \
             patch('modules.weather.requests.get') as mock_geo:

            mock_geo.return_value.json.return_value = {}  # no 'results' key
            mock_geo.return_value.raise_for_status = MagicMock()

            w = WeatherModule(db_conn, TEST_USER)
            result = w.get_weather('CiudadInventada')

        assert result['success'] is False
        assert 'CiudadInventada' in result['result']

    def test_get_weather_forecast_api_error(self, settings, db_conn):
        """Forecast API raises → graceful error with message."""
        with patch('modules.weather.requests_cache.CachedSession') as MockSession:
            mock_session = MagicMock()
            MockSession.return_value = mock_session
            mock_session.get.side_effect = Exception("network error")

            w = WeatherModule(db_conn, TEST_USER)
            result = w.get_weather(None)

        assert result['success'] is False
        assert 'tiempo' in result['result'].lower()

    def test_response_contains_all_expected_fields(self, settings, db_conn):
        """Response format has emoji sections: location, temp, rain/sun, refran."""
        with patch('modules.weather.requests_cache.CachedSession') as MockSession:
            mock_session = MagicMock()
            MockSession.return_value = mock_session
            mock_session.get.return_value.json.return_value = MOCK_FORECAST
            mock_session.get.return_value.raise_for_status = MagicMock()

            w = WeatherModule(db_conn, TEST_USER)
            result = w.get_weather(None)

        text = result['result']
        assert '📍' in text   # location line
        assert '🌡️' in text   # temperature line
        assert '🌧️' in text   # rain/sun line
        assert '🍷' in text   # refran
```

**Step 2: Run to confirm failures**

```bash
pytest tests/test_weather_module.py::TestWeatherModule -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'modules.weather'`

**Step 3: Install requests-cache**

```bash
pip install requests-cache==1.2.1
```

Also add to `requirements.txt` under `# Calendar` section:

```
# Weather
requests-cache==1.2.1
```

**Step 4: Create `modules/weather.py`**

```python
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
    'madrid':  (40.4168, -3.7038, 'ES'),
    'gijón':   (43.5453, -5.6615, 'ES'),
    'gijon':   (43.5453, -5.6615, 'ES'),
    'oviedo':  (43.3619, -5.8494, 'ES'),
    'magán':   (39.9977, -3.7817, 'ES'),
    'magan':   (39.9977, -3.7817, 'ES'),
    'toledo':  (39.8628, -4.0273, 'ES'),
    'sevilla': (37.3882, -5.9823, 'ES'),
    'barcelona': (41.3888, 2.159, 'ES'),
    'valencia': (39.47, -0.3763, 'ES'),
    'bilbao':  (43.263, -2.935, 'ES'),
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
                display_name = city.capitalize()
                # Save if different from current
                current = self._settings.get_weather_location()
                if current['location'].lower() != key:
                    self._settings.set_weather_location(display_name, lat, lon, country)
                    location_updated = True
            else:
                # Try geocoding API
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

        result_text = self._format_response(
            display_name, country, forecast, location_updated
        )
        return {
            'success': True,
            'result': result_text,
            'data': forecast
        }

    def get_location(self) -> dict:
        """Return user's saved weather location."""
        return self._settings.get_weather_location()

    def _geocode(self, city: str) -> Optional[dict]:
        """
        Call OpenMeteo geocoding API.

        Returns dict with name/lat/lon/country or None if not found.
        """
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
            'sunrise': daily['sunrise'][0][-5:],   # "HH:MM"
            'sunset': daily['sunset'][0][-5:],
            'precip_prob': daily['precipitation_probability_max'][0],
        }

    def _format_response(
        self, location: str, country: str, forecast: dict, location_updated: bool
    ) -> str:
        refran = random.choice(_REFRANES)
        temp = forecast['temp']
        temp_min = forecast['temp_min']
        temp_max = forecast['temp_max']
        precip_prob = forecast['precip_prob']
        sunrise = forecast['sunrise']
        sunset = forecast['sunset']

        lines = []
        if location_updated:
            lines.append(f"📌 Ubicación actualizada a {location}.")
        lines.append(f"📍 {location}, {country}")
        lines.append(f"🌡️ Ahora: {temp}°C  |  Hoy: {temp_min}° – {temp_max}°C")
        lines.append(f"🌧️ Lluvia: {precip_prob}%  |  🌅 {sunrise} – 🌇 {sunset}")
        lines.append(f'🍷 "{refran}"')
        return '\n'.join(lines)
```

**Step 5: Run tests**

```bash
pytest tests/test_weather_module.py::TestWeatherModule -v
```

Expected: 6 PASS

**Step 6: Commit**

```bash
git add modules/weather.py requirements.txt tests/test_weather_module.py
git commit -m "feat: add WeatherModule with OpenMeteo + geocoding + refran"
```

---

### Task 4: Router — wire weather module

**Files:**
- Modify: `core/router.py`

**Step 1: Write failing router test**

Add to `tests/test_router.py` (find the existing file, add a new class at the end):

```python
class TestWeatherRouting:
    def test_route_weather_get_no_city(self, router):
        from unittest.mock import patch, MagicMock
        mock_result = {
            'success': True,
            'result': '📍 Madrid, ES\n🌡️ Ahora: 10°C  |  Hoy: 5° – 15°C\n🌧️ Lluvia: 10%  |  🌅 07:45 – 🌇 18:30\n🍷 "refrán"',
            'data': {}
        }
        with patch('core.router.WeatherModule') as MockWeather:
            MockWeather.return_value.get_weather.return_value = mock_result
            result = router.route({'module': 'weather', 'action': 'get', 'city': None})
        assert result['success'] is True
        assert '📍' in result['result']

    def test_route_weather_get_with_city(self, router):
        from unittest.mock import patch, MagicMock
        mock_result = {'success': True, 'result': '📍 Gijón, ES\n...', 'data': {}}
        with patch('core.router.WeatherModule') as MockWeather:
            MockWeather.return_value.get_weather.return_value = mock_result
            result = router.route({'module': 'weather', 'action': 'get', 'city': 'Gijón'})
        assert result['success'] is True
```

**Step 2: Run to confirm failures**

```bash
pytest tests/test_router.py::TestWeatherRouting -v
```

Expected: FAIL — `'weather'` module not handled in router

**Step 3: Add to `core/router.py`**

At the top, add import (after `from modules.calendar import CalendarModule`):

```python
from modules.weather import WeatherModule
```

In the `route()` method, find the `if module == 'calendar':` block and add after it:

```python
            if module == 'weather':
                return self._route_weather(parsed_intent)
```

Add the new private method at the end of the class (after `_route_explain_calendar`):

```python
    def _route_weather(self, parsed: dict) -> dict:
        """Route weather queries."""
        city = parsed.get('city')  # May be None (use saved location)
        weather = WeatherModule(self.conn, self.user_id)
        return weather.get_weather(city)
```

**Step 4: Run tests**

```bash
pytest tests/test_router.py::TestWeatherRouting -v
pytest tests/test_weather_module.py -v
```

Expected: all PASS

**Step 5: Commit**

```bash
git add core/router.py tests/test_router.py
git commit -m "feat: add weather routing to ModuleRouter"
```

---

### Task 5: Haiku parser — weather intents

**Files:**
- Modify: `core/haiku_parser.py`

**Step 1: Update the system prompt in `core/haiku_parser.py`**

Find the module list line (around line 48):
```
- **calendar**: eventos y citas personales...
```
Add after it:
```
- **weather**: consultas del tiempo actual (temperatura, lluvia, amanecer)
```

Find the JSON schema block (the `{{...}}` block with the field list, around line 96-114). Add `"weather"` to the module field and add the new `city` field:

```
  "module": "inventory | shopping | packing | notes | calendar | weather",
```

```
  "city": "nombre de ciudad (para weather, o null para usar ubicación guardada)",
```

Find the examples section (around line 161) and add after the calendar examples:

```python
\"\"\"qué tiempo hace\" → {{\"module\": \"weather\", \"action\": \"get\", \"city\": null}}
\"cómo está el tiempo\" → {{\"module\": \"weather\", \"action\": \"get\", \"city\": null}}
\"va a llover hoy\" → {{\"module\": \"weather\", \"action\": \"get\", \"city\": null}}
\"el tiempo en Gijón\" → {{\"module\": \"weather\", \"action\": \"get\", \"city\": \"Gijón\"}}
\"tiempo en Magán, Toledo\" → {{\"module\": \"weather\", \"action\": \"get\", \"city\": \"Magán\"}}
\"hace frío en Madrid?\" → {{\"module\": \"weather\", \"action\": \"get\", \"city\": \"Madrid\"}}
\"qué temperatura hace\" → {{\"module\": \"weather\", \"action\": \"get\", \"city\": null}}
\"necesito paraguas hoy\" → {{\"module\": \"weather\", \"action\": \"get\", \"city\": null}}
\"\"\"
```

**Step 2: Manual smoke test (no automated test for parser — it calls the real API)**

Start a Python REPL and test parsing (requires ANTHROPIC_API_KEY configured):

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
python -c "
from core.haiku_parser import HaikuParser
p = HaikuParser()
print(p.parse('qué tiempo hace'))
print(p.parse('el tiempo en Gijón'))
print(p.parse('tiempo en Magán'))
"
```

Expected output (approximately):
```python
{'module': 'weather', 'action': 'get', 'city': None}
{'module': 'weather', 'action': 'get', 'city': 'Gijón'}
{'module': 'weather', 'action': 'get', 'city': 'Magán'}
```

**Step 3: Run full test suite to confirm no regressions**

```bash
pytest tests/ -v --tb=short
```

Expected: all previously-passing tests still pass

**Step 4: Commit**

```bash
git add core/haiku_parser.py
git commit -m "feat: add weather intents to Haiku parser"
```

---

### Task 6: End-to-end manual verification

**No code changes — just verification.**

**Step 1: Run complete test suite**

```bash
cd /data/AssistantStudies/sebastian2
source .venv/bin/activate
pytest tests/ -v
```

Expected: all tests pass (55+ from before + ~9 new weather tests)

**Step 2: Quick live API smoke test**

```bash
python -c "
from modules.weather import WeatherModule
from db.connection import get_connection

conn = get_connection()
w = WeatherModule(conn, 'test_smoke')
print('--- Default (Madrid) ---')
r = w.get_weather(None)
print(r['result'])
print()
print('--- Gijón (fallback) ---')
r = w.get_weather('Gijón')
print(r['result'])
print()
print('--- Sevilla (geocoding) ---')
r = w.get_weather('Salamanca')
print(r['result'])
conn.close()
"
```

Expected: Three weather reports with emojis and a refran each. Second call for Gijón should not say "📌 Ubicación actualizada" (it's already in fallback). Third call for Salamanca should say "📌 Ubicación actualizada a Salamanca."

**Step 3: Commit docs updates**

Update `docs/COMANDOS.md` — add weather to the module list and a brief section:

```markdown
### 7. Tiempo (Weather)

**Consultar:**
\```
✅ "qué tiempo hace"
✅ "va a llover hoy"
✅ "el tiempo en Gijón"       → actualiza tu ubicación a Gijón
✅ "tiempo en Magán, Toledo"  → actualiza tu ubicación a Magán
\```

La primera vez usa Madrid. Cada vez que preguntas por una ciudad concreta, la guarda como tu nueva ubicación por defecto.
```

Also update the migration table in `docs/COMANDOS.md`:
```
| 006 | `006_weather_location.sql` | Columnas weather en user_settings |
```

```bash
git add docs/COMANDOS.md
git commit -m "docs: add weather module documentation"
```

---

## Summary

| Task | Files | Tests |
|------|-------|-------|
| 1 | `db/migrations/006_weather_location.sql`, `data/refranes.txt` | manual (DB verify) |
| 2 | `modules/user_settings.py` | `TestWeatherLocation` (3 tests) |
| 3 | `modules/weather.py`, `requirements.txt` | `TestWeatherModule` (6 tests) |
| 4 | `core/router.py` | `TestWeatherRouting` (2 tests) |
| 5 | `core/haiku_parser.py` | manual smoke test |
| 6 | `docs/COMANDOS.md` | full suite regression |

Total new tests: **~11** (3 location + 6 weather + 2 router)
