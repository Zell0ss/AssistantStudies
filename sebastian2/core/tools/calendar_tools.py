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
    },
    # ── Write tools ────────────────────────────────────────────────────────────
    {
        "name": "calendar_add_event",
        "description": (
            "Crea un nuevo evento en el calendario. "
            "Usa esta herramienta cuando el usuario quiera añadir una cita, recordatorio o evento."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título del evento. Ejemplo: 'Dentista', 'Teatro Jovellanos'."
                },
                "date": {
                    "type": "string",
                    "description": "Fecha en formato YYYY-MM-DD. Ejemplo: '2026-03-10'."
                },
                "time": {
                    "type": "string",
                    "description": "Hora en formato HH:MM (24h). Omite si es todo el día. Ejemplo: '10:00'."
                },
                "all_day": {
                    "type": "boolean",
                    "description": "True si el evento es todo el día (sin hora específica)."
                },
                "recurrence_rule": {
                    "type": "string",
                    "description": (
                        "Regla de recurrencia. Valores: 'daily', "
                        "'weekly:MON', 'weekly:MON,WED', 'monthly:15', 'monthly:first-TUE'. "
                        "Omite si es un evento único."
                    )
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "calendar_remove_event",
        "description": (
            "Elimina un evento del calendario por título. "
            "Si hay varios eventos con el mismo nombre, devuelve 'needs_clarification' "
            "con la lista de opciones para que el usuario especifique cuál."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título del evento a eliminar."
                },
                "date": {
                    "type": "string",
                    "description": "Fecha YYYY-MM-DD para desambiguar si hay varios eventos con el mismo nombre."
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "calendar_update_event",
        "description": (
            "Modifica un evento existente: cambia su título, fecha u hora. "
            "Identifica el evento por su título actual (y opcionalmente fecha). "
            "Proporciona solo los campos que cambien."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título actual del evento (para identificarlo)."
                },
                "date": {
                    "type": "string",
                    "description": "Fecha actual YYYY-MM-DD del evento (para desambiguar)."
                },
                "new_title": {
                    "type": "string",
                    "description": "Nuevo título (si se cambia)."
                },
                "new_date": {
                    "type": "string",
                    "description": "Nueva fecha YYYY-MM-DD (si se cambia)."
                },
                "new_time": {
                    "type": "string",
                    "description": "Nueva hora HH:MM (si se cambia)."
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "calendar_add_note",
        "description": (
            "Añade una nota de texto libre a un evento existente (identificado por event_id). "
            "Útil para apuntar 'llevar dinero', 'confirmar cita', etc. junto a un evento. "
            "Usa calendar_search_events o calendar_find_by_datetime primero para obtener el event_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "ID numérico del evento (obtenido con calendar_search_events)."
                },
                "note_text": {
                    "type": "string",
                    "description": "Texto de la nota a añadir al evento."
                }
            },
            "required": ["event_id", "note_text"]
        }
    },
]
