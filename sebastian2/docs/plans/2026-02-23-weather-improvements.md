# Weather Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve geocoding robustness for ambiguous Spanish cities and add multi-day forecast + umbrella/wind alerts.

**Architecture:** All changes confined to `modules/weather.py` (core logic), `core/haiku_parser.py` (new intent examples), `core/router.py` (new action dispatch). No DB migrations needed.

**Tech Stack:** OpenMeteo API (free, no key), requests_cache, Python 3.11, MariaDB, Claude Haiku for intent parsing.

---

### Task 1: Expand fallback cities dict

**Files:**
- Modify: `sebastian2/modules/weather.py:23-35`
- Test: `sebastian2/tests/test_weather_module.py`

**Step 1: Write failing tests**

In `test_weather_module.py`, add a new test class `TestFallbackCities`:

```python
class TestFallbackCities:
    """Test that ambiguous Spanish cities resolve correctly without geocoding."""

    def setup_method(self):
        self.module = WeatherModule(None, "test_user_fallback")

    @patch('modules.weather.WeatherModule._fetch_forecast')
    @patch('modules.weather.WeatherModule._settings')
    def test_salamanca_resolves_to_spain(self, mock_settings, mock_forecast):
        mock_settings.get_weather_location.return_value = {
            'location': '', 'lat': 0.0, 'lon': 0.0, 'country': ''
        }
        mock_settings.set_weather_location = MagicMock()
        mock_forecast.return_value = {
            'temp': 10, 'precip': 0, 'temp_max': 15, 'temp_min': 5,
            'sunrise': '07:30', 'sunset': '18:00', 'precip_prob': 20,
            'windgusts': 20, 'windspeed': 15,
        }
        self.module.get_weather('Salamanca')
        call_args = mock_settings.set_weather_location.call_args
        _, lat, lon, country = call_args[0]
        assert country == 'ES', f"Expected ES, got {country}"
        assert 40.0 < lat < 41.5, f"Lat {lat} outside Salamanca ES range"

    @patch('modules.weather.WeatherModule._fetch_forecast')
    @patch('modules.weather.WeatherModule._settings')
    def test_leon_resolves_to_spain(self, mock_settings, mock_forecast):
        mock_settings.get_weather_location.return_value = {
            'location': '', 'lat': 0.0, 'lon': 0.0, 'country': ''
        }
        mock_settings.set_weather_location = MagicMock()
        mock_forecast.return_value = {
            'temp': 8, 'precip': 0, 'temp_max': 12, 'temp_min': 3,
            'sunrise': '08:00', 'sunset': '18:30', 'precip_prob': 10,
            'windgusts': 15, 'windspeed': 10,
        }
        self.module.get_weather('León')
        call_args = mock_settings.set_weather_location.call_args
        _, lat, lon, country = call_args[0]
        assert country == 'ES', f"Expected ES, got {country}"

    @patch('modules.weather.WeatherModule._fetch_forecast')
    @patch('modules.weather.WeatherModule._settings')
    def test_vitoria_resolves_to_spain(self, mock_settings, mock_forecast):
        mock_settings.get_weather_location.return_value = {
            'location': '', 'lat': 0.0, 'lon': 0.0, 'country': ''
        }
        mock_settings.set_weather_location = MagicMock()
        mock_forecast.return_value = {
            'temp': 9, 'precip': 0, 'temp_max': 13, 'temp_min': 4,
            'sunrise': '07:45', 'sunset': '18:15', 'precip_prob': 15,
            'windgusts': 18, 'windspeed': 12,
        }
        self.module.get_weather('Vitoria')
        call_args = mock_settings.set_weather_location.call_args
        _, lat, lon, country = call_args[0]
        assert country == 'ES', f"Expected ES, got {country}"
```

**Step 2: Run to verify they fail**

```bash
cd /data/AssistantStudies/sebastian2 && source .venv/bin/activate && pytest tests/test_weather_module.py::TestFallbackCities -v
```
Expected: FAIL (KeyError or wrong country).

**Step 3: Expand `_FALLBACK_CITIES` in `modules/weather.py`**

Add these entries to the existing dict (after the `'bilbao'` entry):

```python
    'salamanca':  (40.9701, -5.6635, 'ES'),
    'león':       (42.5987, -5.5671, 'ES'),
    'leon':       (42.5987, -5.5671, 'ES'),
    'granada':    (37.1773, -3.5986, 'ES'),
    'vitoria':    (42.8467, -2.6716, 'ES'),
    'vitoria-gasteiz': (42.8467, -2.6716, 'ES'),
    'córdoba':    (37.8882, -4.7794, 'ES'),
    'cordoba':    (37.8882, -4.7794, 'ES'),
    'valladolid': (41.6523, -4.7245, 'ES'),
    'burgos':     (42.3439, -3.6966, 'ES'),
    'murcia':     (37.9834, -1.1299, 'ES'),
    'alicante':   (38.3452, -0.4810, 'ES'),
    'zaragoza':   (41.6561, -0.8773, 'ES'),
    'pamplona':   (42.8169, -1.6432, 'ES'),
    'santander':  (43.4623, -3.8099, 'ES'),
    'logroño':    (42.4650, -2.4456, 'ES'),
```

**Step 4: Run tests**

```bash
pytest tests/test_weather_module.py::TestFallbackCities -v
```
Expected: PASS (all 3 tests).

**Step 5: Commit**

```bash
git add sebastian2/modules/weather.py sebastian2/tests/test_weather_module.py
git commit -m "feat: expand weather fallback cities to fix ambiguous Spanish city geocoding"
```

---

### Task 2: Smarter geocoding — prefer ES results

**Files:**
- Modify: `sebastian2/modules/weather.py` (the `_geocode` method)
- Test: `sebastian2/tests/test_weather_module.py`

**Step 1: Write failing test**

Add to `TestFallbackCities` (or a new class `TestGeocoding`):

```python
class TestGeocoding:
    """Test geocoding prefers Spanish results when available."""

    def setup_method(self):
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
```

**Step 2: Run to verify they fail**

```bash
pytest tests/test_weather_module.py::TestGeocoding -v
```
Expected: FAIL.

**Step 3: Add `_prefer_spanish_result` and update `_geocode`**

Replace the `_geocode` method in `modules/weather.py`:

```python
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
```

**Step 4: Run tests**

```bash
pytest tests/test_weather_module.py::TestGeocoding tests/test_weather_module.py::TestFallbackCities -v
```
Expected: all PASS.

**Step 5: Commit**

```bash
git add sebastian2/modules/weather.py sebastian2/tests/test_weather_module.py
git commit -m "feat: geocoding prefers Spanish results (count=5, ES-first)"
```

---

### Task 3: Add wind data to forecast fetch

**Files:**
- Modify: `sebastian2/modules/weather.py` (`_fetch_forecast` method)
- Test: `sebastian2/tests/test_weather_module.py`

**Step 1: Write failing test**

```python
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
            }
        }
        module = WeatherModule(None, "test_user_wind")
        result = module._fetch_forecast(40.4, -3.7)
        assert 'windgusts' in result
        assert result['windgusts'] == 45.0
        assert 'windspeed' in result
        assert result['windspeed'] == 25.0
        assert 'weathercode' in result
        assert result['weathercode'] == 2
```

**Step 2: Run to verify fail**

```bash
pytest tests/test_weather_module.py::TestForecastWindData -v
```
Expected: FAIL (KeyError 'windgusts').

**Step 3: Update `_fetch_forecast` in `modules/weather.py`**

Update the method to request wind data and extract it:

```python
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
```

**Step 4: Run tests**

```bash
pytest tests/test_weather_module.py -v
```
Expected: existing tests + new wind test all PASS. (Existing tests will need their mock `json.return_value` updated to include the new fields — fix any that break.)

Note: if existing tests break because mock doesn't include new fields, add the missing keys to their mock response:
```python
'windspeed_10m_max': [20.0],
'windgusts_10m_max': [30.0],
'weathercode': [1],
'precipitation_sum': [0.0],
```

**Step 5: Commit**

```bash
git add sebastian2/modules/weather.py sebastian2/tests/test_weather_module.py
git commit -m "feat: add wind speed, gusts and weathercode to forecast data"
```

---

### Task 4: Umbrella/wind advice in single-day response

**Files:**
- Modify: `sebastian2/modules/weather.py` (`_format_response`, add `_build_advice`)
- Test: `sebastian2/tests/test_weather_module.py`

**Step 1: Write failing tests**

```python
class TestUmbrellaAdvice:
    """_build_advice returns appropriate warnings."""

    def setup_method(self):
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
```

**Step 2: Run to verify fail**

```bash
pytest tests/test_weather_module.py::TestUmbrellaAdvice -v
```
Expected: FAIL (AttributeError: `_build_advice`).

**Step 3: Add `_build_advice` and update `_format_response` in `modules/weather.py`**

Add this method to `WeatherModule`:

```python
# Thresholds
_RAIN_THRESHOLD = 50      # precip_prob % to warn about rain
_WIND_WARN_KMH = 60       # windgusts km/h → moderate wind warning
_WIND_SEVERE_KMH = 75     # windgusts km/h → severe wind warning

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
```

Then update `_format_response` to append advice (add after the rain/sunrise line, before the refran):

```python
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
```

**Step 4: Run tests**

```bash
pytest tests/test_weather_module.py -v
```
Expected: all PASS including new `TestUmbrellaAdvice` tests.

**Step 5: Commit**

```bash
git add sebastian2/modules/weather.py sebastian2/tests/test_weather_module.py
git commit -m "feat: add umbrella and wind alerts to weather response"
```

---

### Task 5: Multi-day forecast — `get_forecast()` method

**Files:**
- Modify: `sebastian2/modules/weather.py` (add `get_forecast`, `_wmo_icon`, `_format_forecast`)
- Test: `sebastian2/tests/test_weather_module.py`

**Step 1: Write failing tests**

```python
class TestMultiDayForecast:
    """get_forecast returns formatted multi-day forecast."""

    def setup_method(self):
        self.module = WeatherModule(None, "test_user_forecast")

    def _make_daily(self, n=7):
        """Helper: make mock daily data for N days starting 2026-02-23."""
        from datetime import date, timedelta
        base = date(2026, 2, 23)
        dates = [(base + timedelta(days=i)).isoformat() for i in range(n)]
        return {
            'dates': dates,
            'temp_max': [15.0] * n,
            'temp_min': [8.0] * n,
            'precip_prob': [30] * n,
            'windspeed': [20.0] * n,
            'windgusts': [35.0] * n,
            'weathercode': [1] * n,
        }

    @patch('modules.weather.WeatherModule._fetch_forecast')
    @patch('modules.weather.WeatherModule._settings')
    def test_week_forecast_returns_7_days(self, mock_settings, mock_forecast):
        mock_settings.get_weather_location.return_value = {
            'location': 'Madrid', 'lat': 40.4, 'lon': -3.7, 'country': 'ES'
        }
        mock_forecast.return_value = self._make_daily(7)
        result = self.module.get_forecast(city=None, time_window='week')
        assert result['success'] is True
        # 7 day lines + header + refran
        lines = result['result'].split('\n')
        day_lines = [l for l in lines if '°' in l]
        assert len(day_lines) == 7

    @patch('modules.weather.WeatherModule._fetch_forecast')
    @patch('modules.weather.WeatherModule._settings')
    def test_weekend_forecast_returns_2_days(self, mock_settings, mock_forecast):
        mock_settings.get_weather_location.return_value = {
            'location': 'Madrid', 'lat': 40.4, 'lon': -3.7, 'country': 'ES'
        }
        mock_forecast.return_value = self._make_daily(7)
        result = self.module.get_forecast(city=None, time_window='weekend')
        assert result['success'] is True
        lines = result['result'].split('\n')
        day_lines = [l for l in lines if '°' in l]
        assert len(day_lines) == 2

    @patch('modules.weather.WeatherModule._fetch_forecast')
    @patch('modules.weather.WeatherModule._settings')
    def test_forecast_includes_wind_warning_line(self, mock_settings, mock_forecast):
        mock_settings.get_weather_location.return_value = {
            'location': 'Madrid', 'lat': 40.4, 'lon': -3.7, 'country': 'ES'
        }
        data = self._make_daily(3)
        data['windgusts'] = [70.0, 30.0, 30.0]
        mock_forecast.return_value = data
        result = self.module.get_forecast(city=None, time_window='week', days=3)
        assert '🌬️' in result['result']

    def test_wmo_icon_sunny(self):
        assert self.module._wmo_icon(0) == '☀️'

    def test_wmo_icon_rain(self):
        assert self.module._wmo_icon(61) == '🌧️'

    def test_wmo_icon_snow(self):
        assert self.module._wmo_icon(71) == '🌨️'

    def test_wmo_icon_storm(self):
        assert self.module._wmo_icon(95) == '⛈️'
```

**Step 2: Run to verify fail**

```bash
pytest tests/test_weather_module.py::TestMultiDayForecast -v
```
Expected: FAIL (AttributeError: `get_forecast`).

**Step 3: Add `_wmo_icon`, `_format_forecast`, `get_forecast` to `WeatherModule`**

```python
def _wmo_icon(self, code: int) -> str:
    """WMO weathercode → emoji icon."""
    if code == 0:
        return '☀️'
    if code <= 3:
        return '🌤️' if code == 1 else ('⛅' if code == 2 else '🌥️')
    if code <= 48:
        return '🌫️'
    if code <= 67:
        return '🌧️'
    if code <= 77:
        return '🌨️'
    if code <= 82:
        return '🌦️'
    return '⛈️'

def _format_forecast(self, location: str, country: str, data: dict, label: str) -> str:
    """Format multi-day forecast data into readable text."""
    from datetime import date as _date
    weekdays_es = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    months_es = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']

    lines = [f"📍 {location}, {country} — {label}\n"]
    for i, date_str in enumerate(data['dates']):
        d = _date.fromisoformat(date_str)
        wd = weekdays_es[d.weekday()]
        mo = months_es[d.month - 1]
        icon = self._wmo_icon(data['weathercode'][i])
        tmin = data['temp_min'][i]
        tmax = data['temp_max'][i]
        rain = data['precip_prob'][i]
        gusts = data['windgusts'][i]

        line = f"{wd} {d.day} {mo}  {icon} {tmin:.0f}°–{tmax:.0f}°  💧{rain}%"
        if gusts >= self._WIND_SEVERE_KMH:
            line += f"  🌪️{gusts:.0f} km/h ⚠️"
        elif gusts >= self._WIND_WARN_KMH:
            line += f"  🌬️{gusts:.0f} km/h"
        lines.append(line)

    refran = random.choice(_REFRANES)
    lines.append(f'\n🍷 "{refran}"')
    return '\n'.join(lines)

def get_forecast(self, city: Optional[str], time_window: str = 'week', days: int = None) -> dict:
    """
    Get multi-day forecast.

    time_window: 'week' (7 days), 'weekend' (next Sat+Sun), or ignored if days given.
    days: explicit number of days to fetch (overrides time_window for fetch).
    """
    from datetime import date as _date, timedelta

    # Resolve location
    if city:
        key = city.lower().strip()
        if key in _FALLBACK_CITIES:
            lat, lon, country = _FALLBACK_CITIES[key]
            display_name = city.title()
        else:
            geo = self._geocode(city)
            if not geo:
                return {
                    'success': False,
                    'result': f"No encontré la ciudad '{city}'.",
                    'data': {}
                }
            display_name, lat, lon, country = geo['name'], geo['lat'], geo['lon'], geo['country']
            self._settings.set_weather_location(display_name, lat, lon, country)
    else:
        saved = self._settings.get_weather_location()
        display_name, lat, lon, country = saved['location'], saved['lat'], saved['lon'], saved['country']

    # Determine how many days to fetch
    fetch_days = days or 7

    try:
        data = self._fetch_forecast(lat, lon, days=fetch_days)
    except Exception as e:
        logger.error(f"Forecast fetch failed: {e}")
        return {'success': False, 'result': "No pude obtener la previsión ahora mismo.", 'data': {}}

    # Filter for weekend if requested
    if time_window == 'weekend' and not days:
        today = _date.today()
        weekend_dates = set()
        for i in range(7):
            d = today + timedelta(days=i)
            if d.weekday() in (5, 6):  # Sat=5, Sun=6
                weekend_dates.add(d.isoformat())
        indices = [i for i, d in enumerate(data['dates']) if d in weekend_dates]
        if not indices:
            return {'success': False, 'result': "No encontré el fin de semana en la previsión.", 'data': {}}
        data = {k: [v[i] for i in indices] if isinstance(v, list) else v for k, v in data.items()}

    labels = {'week': 'Previsión semanal', 'weekend': 'Fin de semana'}
    label = labels.get(time_window, f'Próximos {fetch_days} días')

    result_text = self._format_forecast(display_name, country, data, label)
    return {'success': True, 'result': result_text, 'data': data}
```

**Step 4: Run tests**

```bash
pytest tests/test_weather_module.py -v
```
Expected: all PASS.

**Step 5: Commit**

```bash
git add sebastian2/modules/weather.py sebastian2/tests/test_weather_module.py
git commit -m "feat: add multi-day weather forecast with wind alerts"
```

---

### Task 6: Haiku examples for forecast + wind queries

**Files:**
- Modify: `sebastian2/core/haiku_parser.py`

**Step 1: No new tests needed** — Haiku prompt changes are validated by integration behavior, not unit tests. (The existing parse tests cover basic weather; Haiku model behavior is not unit-testable.)

**Step 2: Add to the schema docstring** — add `forecast` to the action list and `days` field:

In the docstring `action` line, add `forecast` after `get`.
Add to fields:
```
"days": "number of forecast days (optional, for forecast action)"
```

**Step 3: Add examples to the Haiku prompt in `parse()`**

After the existing weather examples (after `"necesito paraguas hoy"`), add:

```python
\"\"\"el tiempo esta semana\"\"\"    → {{\"module\": \"weather\", \"action\": \"forecast\", \"time_window\": \"week\", \"city\": null}}
\"\"\"previsión para esta semana\"\"\"→ {{\"module\": \"weather\", \"action\": \"forecast\", \"time_window\": \"week\", \"city\": null}}
\"\"\"el tiempo el fin de semana\"\"\"→ {{\"module\": \"weather\", \"action\": \"forecast\", \"time_window\": \"weekend\", \"city\": null}}
\"\"\"qué tiempo hace el finde\"\"\"  → {{\"module\": \"weather\", \"action\": \"forecast\", \"time_window\": \"weekend\", \"city\": null}}
\"\"\"el tiempo esta semana en Madrid\"\"\"→ {{\"module\": \"weather\", \"action\": \"forecast\", \"time_window\": \"week\", \"city\": \"Madrid\"}}
\"\"\"previsión 5 días\"\"\"           → {{\"module\": \"weather\", \"action\": \"forecast\", \"days\": 5, \"city\": null}}
\"\"\"necesito paraguas\"\"\"          → {{\"module\": \"weather\", \"action\": \"get\", \"city\": null}}
\"\"\"hace mucho viento hoy?\"\"\"     → {{\"module\": \"weather\", \"action\": \"get\", \"city\": null}}
\"\"\"voy a salir, hay viento?\"\"\"   → {{\"module\": \"weather\", \"action\": \"get\", \"city\": null}}
```

Note: "necesito paraguas" and wind queries map to `action: get` — the enriched response handles the advice automatically.

**Step 4: Run full test suite**

```bash
cd /data/AssistantStudies/sebastian2 && source .venv/bin/activate && pytest tests/ -v
```
Expected: same pass count as before this task (no regressions from prompt changes).

**Step 5: Commit**

```bash
git add sebastian2/core/haiku_parser.py
git commit -m "feat: add forecast action and wind/umbrella query examples to Haiku parser"
```

---

### Task 7: Router dispatch for forecast action

**Files:**
- Modify: `sebastian2/core/router.py` (`_route_weather` method)
- Test: `sebastian2/tests/test_weather_module.py` or `tests/test_router_weather.py`

**Step 1: Write failing test**

Add to `test_weather_module.py` or create a small router test:

```python
class TestWeatherRouter:
    """Router dispatches weather actions correctly."""

    @patch('modules.weather.WeatherModule.get_forecast')
    @patch('modules.weather.WeatherModule._settings')
    def test_router_dispatches_forecast_week(self, mock_settings, mock_forecast):
        from core.router import ModuleRouter
        mock_forecast.return_value = {'success': True, 'result': 'preview', 'data': {}}
        router = ModuleRouter(get_connection(), "test_user_router")
        result = router._route_weather({'action': 'forecast', 'time_window': 'week', 'city': None})
        mock_forecast.assert_called_once()
        assert result['success'] is True

    @patch('modules.weather.WeatherModule.get_forecast')
    @patch('modules.weather.WeatherModule._settings')
    def test_router_dispatches_forecast_weekend(self, mock_settings, mock_forecast):
        from core.router import ModuleRouter
        mock_forecast.return_value = {'success': True, 'result': 'preview', 'data': {}}
        router = ModuleRouter(get_connection(), "test_user_router")
        result = router._route_weather({'action': 'forecast', 'time_window': 'weekend', 'city': None})
        mock_forecast.assert_called_once_with(city=None, time_window='weekend', days=None)
        assert result['success'] is True
```

**Step 2: Run to verify fail**

```bash
pytest tests/test_weather_module.py::TestWeatherRouter -v
```
Expected: FAIL.

**Step 3: Update `_route_weather` in `core/router.py`**

```python
def _route_weather(self, parsed: dict) -> dict:
    """Route weather actions to WeatherModule."""
    action = parsed.get('action')
    city = parsed.get('city')
    weather = WeatherModule(self.conn, self.user_id)
    if action == 'get':
        return weather.get_weather(city)
    if action == 'forecast':
        time_window = parsed.get('time_window', 'week')
        days = parsed.get('days')
        return weather.get_forecast(city=city, time_window=time_window, days=days)
    return {'success': False, 'result': f"Acción de tiempo desconocida: {action}"}
```

**Step 4: Run full suite**

```bash
pytest tests/ -v
```
Expected: all previous passing tests still PASS + new router tests PASS.

**Step 5: Commit**

```bash
git add sebastian2/core/router.py sebastian2/tests/test_weather_module.py
git commit -m "feat: add forecast action dispatch to weather router"
```

---

### Task 8: Update docs

**Files:**
- Modify: `sebastian2/docs/COMANDOS.md` (section 7 Tiempo)

**Step 1: Update the weather section**

Find the `## 7. Tiempo` section and extend it with the new forecast commands and wind/umbrella behavior. Add examples:

```
- "el tiempo esta semana" → previsión de 7 días
- "el tiempo el fin de semana" → sábado y domingo
- "previsión 5 días" → próximos 5 días
- "necesito paraguas" → tiempo de hoy con consejo
- "hace viento hoy?" → tiempo de hoy con aviso de viento si ≥60 km/h
```

Note: "Salamanca, León, Granada, Vitoria, Córdoba, Valladolid, Burgos, Murcia, Alicante, Zaragoza, Pamplona, Santander, Logroño" now in fallback dict.

**Step 2: Run tests (sanity check)**

```bash
pytest tests/ -q
```
Expected: no regressions.

**Step 3: Commit**

```bash
git add sebastian2/docs/COMANDOS.md
git commit -m "docs: update weather section with forecast commands and wind alerts"
```

---

## Summary

| Task | Feature | Tests added |
|---|---|---|
| 1 | Expand fallback cities | 3 |
| 2 | Geocoding prefers ES | 3 |
| 3 | Wind data in forecast | 1 |
| 4 | Umbrella/wind advice | 7 |
| 5 | Multi-day `get_forecast()` | 7 |
| 6 | Haiku forecast examples | 0 (prompt) |
| 7 | Router forecast dispatch | 2 |
| 8 | Docs update | 0 |

**Total new tests: ~23**

Run full suite at any point:
```bash
cd /data/AssistantStudies/sebastian2 && source .venv/bin/activate && pytest tests/ -v
```
