# Weather Module Design — Sebastian 2.0

**Date**: 2026-02-18
**Status**: Approved ✅

---

## Goal

Port weather capability from old Sebastian to Sebastian 2.0. Per-user location stored in DB (default: Madrid). Asking for weather in a new city updates that user's default location. OpenMeteo API (free, no key). Formatted directly in Python with emojis and a Spanish refran.

---

## Architecture

```
"qué tiempo hace en Magán"
  → Haiku parser → {module: "weather", action: "get", city: "Magán"}
  → Router._route_weather(parsed)
  → WeatherModule(conn, user_id)
      → geocode("Magán")           # OpenMeteo geocoding API
      → save location to user_settings
      → fetch_forecast(lat, lon)   # OpenMeteo forecast API (1h cache)
      → format_response()          # Python, emojis + refran
  → {success: True, result: "📍 Magán..."}
```

---

## Data Model — Migration 006

Add weather location columns to `user_settings`:

```sql
ALTER TABLE user_settings
  ADD COLUMN weather_location VARCHAR(100) DEFAULT 'Madrid',
  ADD COLUMN weather_lat      FLOAT        DEFAULT 40.4168,
  ADD COLUMN weather_lon      FLOAT        DEFAULT -3.7038,
  ADD COLUMN weather_country  VARCHAR(50)  DEFAULT 'ES';
```

Default: Madrid (40.4168°N, 3.7038°W). Lat/lon stored to avoid re-geocoding on every request.

---

## Geocoding Strategy

**Primary**: OpenMeteo Geocoding API (free, no auth)
```
GET https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=es&format=json
```
Returns: `name`, `latitude`, `longitude`, `country_code`, `admin1` (region)

**Fallback list** (for known cities if geocoding fails or returns ambiguous results):
```python
_FALLBACK_CITIES = {
    'madrid':  (40.4168, -3.7038, 'ES'),
    'gijón':   (43.5453, -5.6615, 'ES'),
    'gijon':   (43.5453, -5.6615, 'ES'),
    'oviedo':  (43.3619, -5.8494, 'ES'),
    'magán':   (39.9977, -3.7817, 'ES'),
    'magan':   (39.9977, -3.7817, 'ES'),
}
```

---

## WeatherModule API

```python
class WeatherModule:
    def __init__(self, conn, user_id: str): ...

    def get_weather(self, city: str | None) -> dict:
        """
        Get weather for city (or user's saved location if city=None).
        If city provided and different from saved → geocode + save as new default.
        Returns: {success, result, data: {location, temp, temp_max, temp_min,
                  precip, precip_prob, sunrise, sunset, refran}}
        """

    def get_location(self) -> dict:
        """Return user's saved weather location."""
```

**`get_weather` logic:**
1. If `city` is None → use saved location (lat/lon from user_settings)
2. If `city` provided → try fallback dict first (case-insensitive, accent-tolerant)
3. If not in fallback → call geocoding API → on success save to user_settings
4. Fetch forecast with 1h cache
5. Format and return

---

## Forecast API

```
GET https://api.open-meteo.com/v1/forecast
    ?latitude={lat}&longitude={lon}
    &current=temperature_2m,precipitation
    &daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max
    &forecast_days=1&timezone=auto
```

Cache: `requests_cache.CachedSession('.weather_cache', expire_after=3600)`

---

## Response Format

```
📍 Magán, ES
🌡️ Ahora: 8°C  |  Hoy: 5° – 14°C
🌧️ Lluvia: 20%  |  🌅 07:45 – 🌇 18:30
🍷 "Sin pan y sin vino el amor se vuelve frío"
```

If city was updated: prepend `📌 Ubicación actualizada a Magán.\n`

---

## Haiku Parser Intent

New `weather` module with one action: `get`.

```json
{"module": "weather", "action": "get", "city": "Magán"}
{"module": "weather", "action": "get", "city": null}
```

Examples added to system prompt:
```
"qué tiempo hace"          → {module: "weather", action: "get", city: null}
"cómo está el tiempo"      → {module: "weather", action: "get", city: null}
"el tiempo en Gijón"       → {module: "weather", action: "get", city: "Gijón"}
"tiempo en Magán, Toledo"  → {module: "weather", action: "get", city: "Magán"}
"va a llover hoy"          → {module: "weather", action: "get", city: null}
"hace frío en Madrid?"     → {module: "weather", action: "get", city: "Madrid"}
```

---

## Files Changed

| File | Change |
|------|--------|
| `db/migrations/006_weather_location.sql` | New — adds columns to user_settings |
| `modules/weather.py` | New — WeatherModule |
| `data/refranes.txt` | New — copy from `../data/refranes.txt` (124 refranes) |
| `requirements.txt` | Add `requests-cache==1.2.1` |
| `modules/user_settings.py` | Add `get_weather_location`, `set_weather_location` |
| `core/haiku_parser.py` | Add weather module + examples |
| `core/router.py` | Add `_route_weather`, import WeatherModule |
| `tests/test_weather_module.py` | New — unit tests (mock HTTP) |

---

## Testing Strategy

Tests use `unittest.mock.patch` to mock HTTP calls (no real API needed):
- `test_get_weather_default_location` — no city, uses Madrid default
- `test_get_weather_explicit_city` — city="Gijón" from fallback list
- `test_get_weather_updates_location` — new city geocoded, location updated in DB
- `test_get_weather_geocoding_fallback` — geocoding fails, falls back to list
- `test_get_weather_api_error` — graceful error message
- `test_format_response` — correct emoji/text structure

---

## Out of Scope (Phase 2)

- Multi-day forecast
- Weather for packing list suggestions ("¿necesito paraguas en Gijón?")
- Alerts/notifications for rain
