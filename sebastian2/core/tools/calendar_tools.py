"""Calendar tool definitions for Orchestrator."""

FAMILY_SUMMARY = (
    "Calendario: puedo apuntar, consultar y borrar citas y eventos, incluidos los recurrentes, "
    "y te recuerdo la agenda cada mañana."
)

CALENDAR_TOOLS = [
    {
        "name": "calendar_search_events",
        "description": (
            "Busca eventos en el calendario del usuario por palabras del título; usa una o dos palabras clave. "
            "Devuelve una lista de eventos con id, título, fecha (YYYY-MM-DD) y hora (HH:MM o null si todo el día). "
            "Útil para encontrar cuándo tiene algo el usuario (teatro, dentista, vuelo, etc.). "
            # D61: el segundo nivel de la búsqueda devuelve eventos que solo comparten alguna palabra.
            'Un resultado con `coincidencia: "parcial"` puede no ser el evento: no lo muevas ni lo borres sin confirmarlo '
            "con el usuario. Cero resultados no quiere decir que no exista: prueba con otra palabra o con "
            "`calendar_list_events` del rango."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Una o dos palabras del título del evento. Ejemplo: 'teatro', 'dentista', 'vuelo'."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "calendar_list_events",
        "description": (
            "Lista los eventos del calendario en un rango de tiempo. "
            "Devuelve todos los eventos del período con id, título, fecha y hora. "
            "Para «el mes que viene», `next_month`; para un mes con nombre («diciembre», «en enero»), `YYYY-MM`, "
            "con el año que toque desde hoy (si ya pasó ese mes este año, el siguiente). "
            "Lo que el usuario tiene que hacer (pasos, preparaciones) no está aquí: está en `compromisos_listar`."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_window": {
                    "type": "string",
                    "description": (
                        "Rango de tiempo. Valores válidos: "
                        "'today' (hoy), 'tomorrow' (mañana), 'week' (los próximos 7 días), "
                        "'month' (lo que queda de este mes, desde hoy), 'next_month' (el mes siguiente, entero), "
                        "'weekend' (próximo sábado y domingo) o 'YYYY-MM' (un mes concreto, entero; "
                        "por ejemplo '2026-12'). Cualquier otro valor da error."
                    ),
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
            "Usa esta herramienta cuando el usuario quiera añadir una cita, recordatorio o evento. "
            "Si el usuario no da día y hora, no te los inventes: pregunta con `request_clarification`. "
            'Un recordatorio sin hora ("recuérdame acostarme pronto") no es un evento. '
            "Busca antes si la cita ya existe con `calendar_search_events`: si el usuario habla de una cita que ya tiene "
            "(para añadirle algo, moverla o ligar pasos a ella), no la crees otra vez. Si devuelve `exists`, usa ese "
            "evento (su `event_id`), no lo crees de nuevo."
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
                    "description": (
                        "Fecha en formato YYYY-MM-DD. Ejemplo: '2026-03-10'. Si el usuario da solo día y mes, el año es "
                        "el de la fecha de hoy, o el siguiente si ese día ya pasó."
                    )
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
            "Busca antes el evento con `calendar_search_events` y pasa su `event_id`: es lo más seguro. "
            "Sin id, se identifica por su título actual (y opcionalmente fecha). "
            "Proporciona solo los campos que cambien. "
            "Si dice que no lo ha encontrado, pregunta al usuario: no lo crees de nuevo con `calendar_add_event`."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "ID del evento (de calendar_search_events). Si viene, manda sobre el título."
                },
                "title": {
                    "type": "string",
                    "description": "Título actual del evento (para identificarlo si no tienes el event_id)."
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
                    "description": (
                        "Nueva fecha YYYY-MM-DD (si se cambia). Si el usuario da solo el día («al 29»), el mes y el "
                        "año son los de la fecha actual del evento, salvo que diga otros."
                    )
                },
                "new_time": {
                    "type": "string",
                    "description": "Nueva hora HH:MM (si se cambia)."
                }
            }
        }
    },
    {
        "name": "calendar_get_tickets",
        "description": (
            "Obtiene las entradas o tickets (QR, códigos de barras) almacenados en un evento. "
            "Devuelve una lista de tickets con su tipo y valor. "
            "Usa calendar_search_events primero para obtener el event_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "ID numérico del evento (obtenido con calendar_search_events)."
                }
            },
            "required": ["event_id"]
        }
    },
    {
        "name": "calendar_clear_tickets",
        "description": (
            "Elimina todos los tickets almacenados en un evento. "
            "Usa calendar_search_events primero para obtener el event_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "ID numérico del evento."
                }
            },
            "required": ["event_id"]
        }
    },
    {
        "name": "calendar_add_note",
        "description": (
            "Añade una nota de texto libre a un evento existente. "
            "Útil para apuntar 'llevar dinero', 'confirmar cita', etc. junto a un evento. "
            "También para los datos de una cita: lugar, planta, teléfono, código, quién acompaña. "
            "**Nunca** resultados ni diagnósticos. "
            "Identifica el evento por su `event_id` (de calendar_search_events) o, sin él, por `title` y `date`: "
            "una sola llamada, sin buscar antes. Si dice que hay varios, pregunta al usuario cuál; si no lo ha "
            "encontrado, pregunta: no lo crees de nuevo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "integer",
                    "description": "ID numérico del evento (obtenido con calendar_search_events). Si viene, manda sobre el título."
                },
                "title": {
                    "type": "string",
                    "description": "Título del evento (para identificarlo si no tienes el event_id). Ejemplo: 'Endoscopia'."
                },
                "date": {
                    "type": "string",
                    "description": "Día del evento YYYY-MM-DD (para desambiguar si hay varios con ese título)."
                },
                "note_text": {
                    "type": "string",
                    "description": "Texto de la nota a añadir al evento."
                }
            },
            "required": ["note_text"]
        }
    },
]
