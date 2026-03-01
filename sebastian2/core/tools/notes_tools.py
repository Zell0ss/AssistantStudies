"""Notes tool definitions for Orchestrator."""

NOTES_TOOLS = [
    {
        "name": "notes_search",
        "description": (
            "Busca en las notas del usuario por contenido o texto libre. "
            "Devuelve lista de notas con id, contenido y tags. "
            "Útil para recordar información guardada previamente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texto a buscar en el contenido de las notas."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "notes_get",
        "description": (
            "Obtiene una nota específica por su ID numérico. "
            "Devuelve el contenido completo y los tags."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "ID numérico de la nota."
                }
            },
            "required": ["note_id"]
        }
    }
]
