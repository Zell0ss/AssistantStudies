"""Compromisos tool definitions for Orchestrator (fase 3, D45, D49-D52): cosas que el usuario tiene que hacer,
con día, hora o intervalo, sueltas o atadas a una cita del calendario.

Las descripciones llevan el contrato del plan §2.2. Nombran qué hacer con lo que NO es un compromiso (cita, dato,
registro de salud) en vez de solo prohibir (lección de R5)."""

FAMILY_SUMMARY = (
    "Compromisos: apunto lo que tienes que hacer un día o a una hora (también los pasos de preparar una cita, "
    "ligados a ella), te lo cuento en el resumen de la mañana y te aviso a su hora."
)

COMPROMISOS_TOOLS = [
    {
        "name": "compromisos_crear",
        "description": (
            'Para cosas que el usuario **tiene que hacer** en un día o a una hora: "el lunes empiezo la dieta", '
            '"la víspera a las 21:00, la primera toma". Crea varias a la vez: los pasos de una preparación se dictan '
            "en un mensaje, una sola llamada con todos. Si van ligadas a una cita del calendario, usa su `evento_id` "
            "y desfases (`dias_inicio`, `minutos`) en vez de fechas, para que se muevan con la cita: busca antes el "
            "evento con `calendar_search_events` o `calendar_find_by_datetime`. Sin cita, usa `fecha_inicio` (y "
            "`fecha_fin` si dura varios días). Devuelve cada compromiso con su momento ya calculado: repítelo al "
            "usuario con esas fechas. Un intervalo («tres días antes y hasta la víspera») es **un solo compromiso** con "
            "`dias_inicio` y `dias_fin`, no uno por día ni uno de «empezar» y otro de «mantener». **No para citas** (eso es `calendar_add_event`), **ni para datos** (eso es "
            "`mark_as_memorable`), **ni para registros de salud** (eso es `salud`). Si un paso depende de algo que no "
            'sabes ("si toma zinc"), pregunta antes con `request_clarification`; si no aplica, no lo crees.'
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 20,
                    "description": "Los compromisos a crear, de 1 a 20.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "texto": {
                                "type": "string",
                                "description": (
                                    "Qué hay que hacer, en una frase que se entienda sola. "
                                    "Ejemplo: '2.ª toma del preparado (sobres A y B en ½ l)'."
                                ),
                            },
                            "evento_id": {
                                "type": "integer",
                                "description": (
                                    "ID del evento del calendario al que va atado (de calendar_search_events). "
                                    "Con él, el momento se da con dias_inicio o minutos, nunca con fechas."
                                ),
                            },
                            "fecha_inicio": {
                                "type": "string",
                                "description": "Solo sin evento_id: día YYYY-MM-DD. Ejemplo: '2026-12-14'.",
                            },
                            "fecha_fin": {
                                "type": "string",
                                "description": (
                                    "Solo sin evento_id: último día YYYY-MM-DD si dura varios días "
                                    "(inclusive). Un intervalo no lleva hora."
                                ),
                            },
                            "dias_inicio": {
                                "type": "integer",
                                "description": (
                                    "Solo con evento_id: días respecto al día del evento. -3 = tres días antes, "
                                    "-1 = la víspera, 0 = el mismo día."
                                ),
                            },
                            "dias_fin": {
                                "type": "integer",
                                "description": (
                                    "Solo con evento_id: último día del intervalo, también respecto al evento "
                                    "(la dieta de tres días antes hasta la víspera: dias_inicio -3, dias_fin -1)."
                                ),
                            },
                            "hora": {
                                "type": "string",
                                "description": (
                                    "Hora de reloj HH:MM (24 h) de ese día. Omite si no tiene hora. "
                                    "No va con minutos ni con un intervalo."
                                ),
                            },
                            "minutos": {
                                "type": "integer",
                                "description": (
                                    "Solo con evento_id: desfase en minutos respecto a la HORA del evento. "
                                    "-180 = tres horas antes. No va con dias_* ni con hora."
                                ),
                            },
                        },
                        "required": ["texto"],
                    },
                },
            },
            "required": ["items"],
        },
    },
    {
        "name": "compromisos_listar",
        "description": (
            "Lista los compromisos pendientes del usuario, con su momento ya calculado y en orden. Sin fechas, "
            "de hoy a 14 días. Útil para 'qué tengo que hacer esta semana', 'qué me falta para la cita'. "
            "Para el id de uno que hay que completar o borrar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "desde": {"type": "string", "description": "Primer día de la ventana, YYYY-MM-DD. Por defecto, hoy."},
                "hasta": {"type": "string", "description": "Último día de la ventana, YYYY-MM-DD. Por defecto, desde + 14 días."},
                "evento_id": {"type": "integer", "description": "Solo los de esta cita (de calendar_search_events)."},
            },
            "required": [],
        },
    },
    {
        "name": "compromisos_completar",
        "description": (
            "Marca un compromiso como hecho. Úsalo cuando el usuario dice que ya lo ha hecho ('ya tomé la primera "
            "parte'). Usa compromisos_listar primero para obtener el id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID del compromiso (de compromisos_listar)."},
            },
            "required": ["id"],
        },
    },
    {
        "name": "compromisos_borrar",
        "description": (
            "Quita un compromiso. Con motivo `olvidar` lo borra de verdad, sin dejar rastro: cuando el usuario dice "
            "'olvida ese compromiso' o 'borra eso'. Con motivo `cancelar` lo deja cancelado: cuando dice 'ya no hace "
            "falta'. Usa compromisos_listar primero para obtener el id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID del compromiso (de compromisos_listar)."},
                "motivo": {
                    "type": "string",
                    "enum": ["olvidar", "cancelar"],
                    "description": "`olvidar` = borrarlo del todo. `cancelar` = ya no hace falta, queda cancelado.",
                },
            },
            "required": ["id", "motivo"],
        },
    },
]
