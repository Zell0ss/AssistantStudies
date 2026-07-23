"""Notes tool definitions for Orchestrator."""

FAMILY_SUMMARY = (
    "Notas: puedo guardar notas de texto libre, etiquetarlas y recuperarlas después buscando "
    "por contenido."
)

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
    },
    # ── Write tools ────────────────────────────────────────────────────────────
    {
        "name": "notes_create",
        "description": (
            "Crea una nota nueva con contenido de texto libre y opcionalmente tags. "
            "Devuelve el note_id de la nota creada. "
            "Usa para guardar información, recordatorios o apuntes del usuario."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Contenido de la nota."
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de etiquetas opcionales. Ejemplo: ['receta', 'pendiente']."
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "notes_append",
        "description": (
            "Añade texto al final de una nota existente. "
            "Útil cuando el usuario quiere ampliar una nota que ya tiene. "
            "Usa notes_search primero para obtener el note_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "ID numérico de la nota."
                },
                "text": {
                    "type": "string",
                    "description": "Texto a añadir al final de la nota."
                }
            },
            "required": ["note_id", "text"]
        }
    },
    {
        "name": "notes_add_tag",
        "description": (
            "Añade un tag a una nota existente. "
            "Usa notes_search primero para obtener el note_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "ID numérico de la nota."
                },
                "tag": {
                    "type": "string",
                    "description": "Tag a añadir. Ejemplo: 'urgente', 'receta'."
                }
            },
            "required": ["note_id", "tag"]
        }
    },
    {
        "name": "notes_remove_tag",
        "description": (
            "Elimina un tag de una nota existente. "
            "Usa notes_search primero para obtener el note_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "ID numérico de la nota."
                },
                "tag": {
                    "type": "string",
                    "description": "Tag a eliminar."
                }
            },
            "required": ["note_id", "tag"]
        }
    },
    {
        "name": "notes_delete",
        "description": (
            "Elimina permanentemente una nota. "
            "Usa notes_search primero para confirmar el note_id correcto antes de borrar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note_id": {
                    "type": "integer",
                    "description": "ID numérico de la nota a eliminar."
                }
            },
            "required": ["note_id"]
        }
    },
]
