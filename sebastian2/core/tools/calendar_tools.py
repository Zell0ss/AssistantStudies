"""Calendar tool definitions for Orchestrator."""

CALENDAR_TOOLS = [
    {
        "name": "calendar_search_events",
        "description": (
            "Busca eventos en el calendario del usuario por texto en el título. "
            "Devuelve una lista de eventos con id, título, fecha (YYYY-MM-DD) y hora (HH:MM o null si todo el día). "
            "Útil para encontrar cuándo tiene algo el usuario (teatro, dentista, vuelo, etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texto a buscar en el título del evento. Ejemplo: 'teatro', 'dentista', 'vuelo'."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "calendar_list_events",
        "description": (
            "Lista los eventos del calendario en un rango de tiempo. "
            "Devuelve todos los eventos del período con id, título, fecha y hora."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_window": {
                    "type": "string",
                    "description": (
                        "Rango de tiempo. Valores válidos: "
                        "'today' (hoy), 'tomorrow' (mañana), 'week' (esta semana), "
                        "'month' (este mes), 'weekend' (próximo fin de semana)."
                    ),
                    "enum": ["today", "tomorrow", "week", "month", "weekend"]
                }
            },
            "required": ["time_window"]
        }
    },
    {
        "name": "calendar_find_by_datetime",
        "description": (
            "Busca un evento por fecha y hora exactas. "
            "Útil cuando el usuario menciona 'la cita de las 19:00 del miércoles'. "
            "Devuelve el evento si existe, o null."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Fecha en formato YYYY-MM-DD. Ejemplo: '2026-03-05'."
                },
                "time": {
                    "type": "string",
                    "description": "Hora en formato HH:MM (24h). Ejemplo: '19:00'."
                }
            },
            "required": ["date", "time"]
        }
    }
]
