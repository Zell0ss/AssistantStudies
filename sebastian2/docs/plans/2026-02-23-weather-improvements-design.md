# Weather Improvements — Design Doc

**Date:** 2026-02-23
**Status:** Approved

## Option B — Geocoding robustness

### Problem
`_geocode()` uses `count=1` → OpenMeteo returns the most-populated city globally →
"Salamanca" resolves to Salamanca, México (900k hab.) instead of Salamanca, España (140k).

### Solution: two-tier approach
1. **Expand `_FALLBACK_CITIES`** with Spanish cities whose names are ambiguous globally:
   Salamanca, León, Granada, Vitoria-Gasteiz, Córdoba, Valladolid, Burgos

2. **`_geocode()` smarter fallback**: when city not in hardcoded dict, fetch `count=5`
   and prefer any result with `country_code=ES` via `_prefer_spanish_result()` helper.
   If none is ES, return the first result (existing behavior).

No changes to Haiku or router needed.

---

## Option D — Multi-day forecast + umbrella/wind advice

### New OpenMeteo fields
Add to daily params: `windspeed_10m_max`, `windgusts_10m_max`, `precipitation_sum`
Add: `weathercode` (WMO code for weather condition → icon mapping)

### Enriched single-day `get_weather()` (action: get)
`_format_response()` calls new `_build_advice()` helper:
- Precip prob ≥ 50% → "☂️ Lleve paraguas, señor."
- Windgusts ≥ 60 km/h → "🌬️ Ráfagas de X km/h — tome precauciones."
- Windgusts ≥ 75 km/h → "🌪️ Viento severo (X km/h) — evite salir si puede."

"necesito paraguas?" → parsed as `action: get` → same enriched response.

### New multi-day `get_forecast()` (action: forecast)
Haiku new action + fields:
```json
{"module": "weather", "action": "forecast", "time_window": "week"}
{"module": "weather", "action": "forecast", "time_window": "weekend"}
{"module": "weather", "action": "forecast", "days": 5}
```
`time_window: "week"` = today + 6 days (7 total).
`time_window: "weekend"` = next Saturday + Sunday.
`days: N` = today + N-1 days.

Response format:
```
📍 Madrid, ES — Previsión semanal

Lun 23 feb  🌤  8°–14°  💧30%
Mar 24 feb  🌧  9°–12°  💧80%  🌬️55 km/h
Mié 25 feb  ⛅ 10°–15°  💧20%  🌪️78 km/h ⚠️
...
🍷 "refran"
```
WMO weathercode → icon: 0=☀️, 1-3=🌤/⛅/🌥, 45-48=🌫, 51-67=🌧, 71-77=🌨, 80-82=🌦, 95+=⛈

### Files touched
| File | Change |
|---|---|
| `modules/weather.py` | `_FALLBACK_CITIES` expanded, `_geocode()` + `_prefer_spanish_result()`, `_fetch_forecast(days)`, `_build_advice()`, `get_forecast()` |
| `core/haiku_parser.py` | `forecast` action + examples (week/weekend/paraguas) |
| `core/router.py` | `_route_weather()` handles `forecast` action |
| `tests/test_weather_module.py` | New tests for each new behavior |
| `docs/COMANDOS.md` | Update sección 7 Tiempo |
